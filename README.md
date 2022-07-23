# Linux Statistic collector to MQTT

I have written this script(s) being inspired by this: https://github.com/andres-leon/rbp-mqtt-stats
I just "expanded" it a bit with my own vision :smile:

# Python 3 requirments

This script need a those modules:
```
paho-mqtt psutil
```

Install them via python3-pip *(if you have already install python3-pip then skip first line)*:
```
$ sudo apt install python3-pip
$ sudo pip3 install paho-mqtt psutil
```

# Usage

Copy script to desired directory, set it as executable ( ```chmod +x linux-stat-mqtt.py```).

Open script that you're interrested (with or without Nvidia GPU temperature monitoring), modify at header configuration (mqtt host, password, user, extra options).

Add script to crontab:
```
$ crontab -e
```
e.g. to run every 10min, with script in ```/home/pi/linux-stat-mqtt/linux-stat-mqtt.py``` add this line to crontab:
```
*/10 * * * * /home/pi/linux-stat-mqtt/linux-stat-mqtt.py > /tmp/linux-stat-mqtt-last-log.log 2>&1
```

