import time
import os
import sys
import platform
import subprocess
import psutil
from time import strftime
import datetime
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import argparse

topics = {'ram': 'ram_used_percentage',
          'cpu': 'cpu_used_percentage',
          'disk': 'disk_used_percentage',
          'os': 'operating_system',
          'time': 'message_time',
          'battery_level': 'battery_level_percentage',
          'battery_charging': 'battery_charging',
          'shutdown': 'shutdown_command',
          'reboot': 'reboot_command',
          'lock': 'lock_command'}


#Delay in second
message_send_delay = 10
client_connected = False
connection_failed = False

commands = {
    'Windows': {
        'shutdown': 'shutdown /s',
        'reboot': 'shutdown /r',
        'lock': {
            'base': 'rundll32.exe user32.dll,LockWorkStation'
        }
    },
    'macOS': {
        'shutdown': 'sudo shutdown -h now',
        'reboot': 'sudo reboot',
        'lock': {
            'base': 'pmset displaysleepnow'
        }
    },
    'Linux': {
        'shutdown': 'sudo shutdown -h now',
        'reboot': 'sudo reboot',
        'lock': {
            'gnome': 'gnome-screensaver-command -l',
            'cinnamon': 'cinnamon-screensaver-command -a',
            'i3': 'i3lock'
        }
    }
}


def Get_RAM_Percentage():
    return psutil.virtual_memory()[2]


def Get_CPU_Percentage():
    return psutil.cpu_percent()


def Get_Disk_Used_Percentage():
    return psutil.disk_usage('/')[3]


def Get_Operating_System():
    os = platform.system()
    if os == 'Darwin':  # It's macOS
        return 'macOS'
    return os


def Get_Battery():
    battery = psutil.sensors_battery()
    if battery:  # Then the device has a battery
        return {'level': battery.percent, 'charging': battery.power_plugged}
    else:
        return {'level': 'None', 'charging': 'None'}


def Get_Desktop_Environment():
    if not args.desktop_environment:
        de = os.environ.get('DESKTOP_SESSION')
        if de != None:
            return de
        else:
            return "base"
    else:
        return args.desktop_environment


def Get_Time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def Shutdown():
    print("I am going to shutdown the computer")
    command = commands[Get_Operating_System()]['shutdown']
    subprocess.Popen(command.split(), stdout=subprocess.PIPE)


def Reboot():
    print("I am going to reboot the computer")
    command = commands[Get_Operating_System()]['reboot']
    subprocess.Popen(command.split(), stdout=subprocess.PIPE)


def Lock():
    print("I am going to lock the computer")
    command = commands[Get_Operating_System(
    )]['lock'][Get_Desktop_Environment()]
    subprocess.Popen(command.split(), stdout=subprocess.PIPE)


def on_connect(client, userdata, flags, rc):
    # Quando ho la connessione mi iscrivo ai topic per ricevere i comandi
    # Inserisco qua le subscription per eseguirle anche al riavvio del server
    global client_connected
    if rc == 0:  # Se la connessione è riuscita
        print("Connection established")
        client_connected = True
        client.subscribe(GetTopic('shutdown'))
        client.subscribe(GetTopic('reboot'))
        client.subscribe(GetTopic('lock'))
    else:
        print("Can't connect")


def on_message(client, userdata, message):
    if message.topic == GetTopic('shutdown'):
        Shutdown()
    elif message.topic == GetTopic('reboot'):
        Reboot()
    elif message.topic == GetTopic('lock'):
        Lock()
    else:
        print("Unknown topic: " + message.topic)


def on_disconnect(client, userdata, rc):
    global client_connected
    print("Connection lost")
    client_connected = False


def ParseArguments():
    # Parse arguments
    global args

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--broker', dest='broker', type=str, required=True,
                        help="MQTT Broker")
    parser.add_argument('-n', '--name', dest='name', type=str, required=True,
                        help="Client name")
    parser.add_argument('-u', '--username', dest='username', type=str, default='', required=False,
                        help='Broker username (default set to ""')
    parser.add_argument('-p', '--password', dest='password', type=str, default='', required=False,
                        help='Broker password (default set to ""')
    parser.add_argument('-de', '--desktop-environment', dest='desktop_environment', type=str, default=None, required=False,
                        help='Desktop environment (to use if it\'s wrongly detected)')
    args, unknown = parser.parse_known_args()


def GetTopic(name):
    main_topic = "monitor/" + args.name + "/"
    if name in topics:
        return main_topic + topics[name]
    else:
        return


def Main():
    ParseArguments()
    print("Broker: " + args.broker)
    print("OS: " + Get_Operating_System())
    print("Desktop Environment: " + Get_Desktop_Environment())
    print("Message send every " + str(message_send_delay) + " seconds")

    # Preparo il client
    client = mqtt.Client("monitor-" + args.name)
    client.username_pw_set(args.username, args.password)
    client.on_message = on_message
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Mi connetto al server in modo asincrono:
    # se il server non è raggiungibile, appena sarà possibile avverrà la connessione
    client.connect_async(args.broker)

    # Inizio il loop di invio dei dati ogni {delay} secondi
    client.loop_start()

    while True:
        if client_connected:
            # Invio la % della RAM usata
            client.publish(GetTopic('ram'), Get_RAM_Percentage())
            # Invio la % della CPU usata
            client.publish(GetTopic('cpu'), Get_CPU_Percentage())
            # Invio la % del disco usato
            client.publish(GetTopic('disk'), Get_Disk_Used_Percentage())
            # Invio il Sistema Operativo
            client.publish(GetTopic('os'), Get_Operating_System())
            # Invio l'ora attuale
            client.publish(GetTopic('time'), Get_Time())
            # Invio lo stato della batteria
            battery_status = Get_Battery()
            client.publish(GetTopic('battery_level'), battery_status['level'])
            client.publish(GetTopic('battery_charging'),
                           battery_status['charging'])

        time.sleep(message_send_delay)


Main()
