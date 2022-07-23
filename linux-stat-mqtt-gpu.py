#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# to install: psutil
# NOTICE: this script also try collect nvidia gpu stats using 'nvidia-smi' (part of nvidia proprietary driver)
import time, datetime, math, sys
import psutil, subprocess
import xml.etree.ElementTree
import paho.mqtt.client as mqtt, json

collect_gpu = 1
combined_disk_usage = 0
cpu_usage_measure_time_sec = 30

mqtt_enabled = 1
# host, port, user, pass, topic - no need to explain
# retain - mark last message as "last known good" message
# disk_totals - this sum-up all disks/parts total, used & percent (weightned) and return it, 
#   if "0" , then each disk info is retuend as object within node (with disk oject name "/dev/xxxx"): 
#      disks:{ (object_name)"/dev/xxxx":{ total:[disk_totalMiB], used:[disk_usedMiB], pc:[disk_used_percent]} }
# disk_human_units - 1= use human units (MiB, GiB, TiB - return size in auto-scaled value in string format)
#                    0= return all sizes in MiB
# time_in_unix - return time in unix timestamp format (secs since 1970-01-01 00:00) /uptime is returned in secs since boot/
mqtt_conf = { 
	'host': '192.168.100.200', 'port': 1883, 'user': 'unixstats', 'pass': 'thepassword', 
	'topic':'home/server/sever1', "retain": True,
	'disk_totals': 1,
	'disk_human_units': 1,
	'time_in_unix': 0
	}
 

def get_cpu_temp():
	temp = -1.0
	# this can be different, bot for most systems should be ok
	# comment/uncomment proper line
	path = "/sys/class/thermal/thermal_zone0/temp"
	# for old laptop compal, this is proper path to get real CPU temperature:
	# you can check this via "sensors" command (part of package "lm-sensors")
	# path = "/sys/devices/platform/compal-laptop/hwmon/hwmon0/temp1_input"
	with open(path,"r") as f:
		temps = f.read(16)
		temp = int(temps) * 0.001
	temp = round(temp,1)
	return temp
	
def get_nvidia_gpu_temp():
	temp = -1.0
	try:
		# for hardware equipped with nvidia gpu to use this. You have to install dedicated drivers for your graphic card first.
		res = subprocess.run(['/usr/bin/nvidia-smi','-q','--id=0','--xml-format'],stdout=subprocess.PIPE)
		try:
			xr = xml.etree.ElementTree.ElementTree(xml.etree.ElementTree.fromstring(res.stdout))
			f = xr.findall(".//gpu_temp")
			txt = f[0].text # output "48 C"
			txts = txt.split() # split at space to have temp. value sperated
			#print(txts)
			temp = float(txts[0]) # convert temp to float
		except:
			print("ERROR: XML parse error. nvidia-smi output: {}".format(res.stdout))
	except:
		print("ERROR: nvidia-smi not found or returned non-0 exit code.")
		
	return temp

def get_up_time_str(secs):
	secs = int(secs)
	dy, rem = divmod(secs, 86400)
	hr, rem = divmod(rem, 3600)
	mn, sc = divmod(rem, 60)
	s = "{:0d} days, {:02d}:{:02d}:{:02d}".format(dy,hr,mn,sc)
	return s

def size_to_human(sz):
	sz = int(sz)
	re = sz
	res = "{} bytes".format(sz)
	if (sz > (1024*1024*1048576)):
		# TiB
		re = round(sz/(1024*1024*1048576)*1.0, 2)
		res = "{:3.2f} TiB".format(re)
	elif (sz > (1024*1048576)):
		# GiB
		re = round(sz/(1024*1048576)*1.0, 2)
		res = "{:3.2f} GiB".format(re)
	elif (sz > 1048576):
		# MiB
		re = round(sz/1048576.0, 2)
		res = "{:3.2f} MiB".format(re)
	elif (sz > 1024):
		# KiB
		re = round(sz/1024.0, 3)
		res = "{:3.3f} KiB".format(re)

	return (re, res, )

# calc curent, boot, uptime
curr_time_ts = time.time()
curr_time = datetime.datetime.fromtimestamp(curr_time_ts).strftime("%Y-%m-%d %H:%M:%S")
boot_time_ts = psutil.boot_time()
boot_time = datetime.datetime.fromtimestamp(boot_time_ts).strftime("%Y-%m-%d %H:%M:%S")
up_time_p = curr_time_ts - boot_time_ts
up_time_td = datetime.timedelta(seconds=up_time_p)
#up_time = "{:0d} days, {:02d}:{:02d}:{02d}".format(up_time_td.days, up_time_td.hours, up_time_td.minutes, up_time_td.seconds)
up_time = get_up_time_str(up_time_td.total_seconds())
cpu_usage = psutil.cpu_percent(cpu_usage_measure_time_sec)
v_mem_usage = psutil.virtual_memory().percent
v_mem_avail = psutil.virtual_memory().available
v_mem_total = psutil.virtual_memory().total
v_mem_avail_s = size_to_human(v_mem_avail)[1]

cpu_t = get_cpu_temp()

if (collect_gpu != 0):
	gpu_t = get_nvidia_gpu_temp()

# first get list of disk/partitions
parts = psutil.disk_partitions()
disku = []
disks_total_used = 0
disks_total_size = 0
for part in parts:
	du = psutil.disk_usage(part.mountpoint)
	# debug prints
	#print("Device: {}".format(part.device))
	#print(du)
	#print("dev={} mnt={} fs={} sz={} free={} used={} prc={}".format(part.device, part.mountpoint, part.fstype, du.total, du.free, du.used, du.percent))
	##
	dui = {'dev': part.device, 'mnt': part.mountpoint, 'fs': part.fstype, 'sz': du.total, 'szm': int(math.floor(du.total/1048576)), 'free': du.free, 'freem': int(math.floor(du.free/1048576)), 'used': du.used, 'usedm': int(math.floor(du.used/1048576)), 'pc':du.percent}
	disku.append(dui)
	disks_total_size = disks_total_size + du.total
	disks_total_used = disks_total_used + du.used
	# debug print
	#print(dui)

# calculate precent used weightned by partition/disk size
disks_total_prc = 0.0
for d in disku:
	p = d['pc']
	w = disks_total_size / d['sz']
	pw = p / w
	disks_total_prc = disks_total_prc + pw
	# debug print
	#print("Disk: {} - pc={} sz={} weight={} pw={}".format(d['dev'], p, d['sz'], w, pw))

disks_total_size_s = size_to_human(disks_total_size)[1]
disks_total_used_s = size_to_human(disks_total_used)[1]
disks_total_prc = round(disks_total_prc, 2)
## ---------- PRINT OUT -------------
if (collect_gpu != 0):
	print("GPU temperature: {}\u00b0C".format(gpu_t))
	
print("CPU temperature: {}\u00b0C".format(cpu_t))
print("CPU usage: {}".format(cpu_usage))
print("Current time: {} ({})".format(curr_time, curr_time_ts))
print("Boot time: {} ({})".format(boot_time,boot_time_ts))
print("Up time: {} ({})".format(up_time,up_time_p))

print("Virtual memory total: {} ({})".format(size_to_human(v_mem_total)[1], v_mem_total))
print("Virtual memory available: {} ({})".format(v_mem_avail_s, v_mem_avail))
print("Virtual memory usage: {:5.2f} %".format(v_mem_usage))

print("Disks total size : {} ({})".format(disks_total_size_s,disks_total_size))
print("Disks total used : {} ({})".format(disks_total_used_s,disks_total_used))
print("Disks total usage: {:3.2f} %".format(disks_total_prc))
if (combined_disk_usage == 0):
	print("Detailed disk usage:")
	# calc fields max size
	f1 = 0
	f2 = 0
	for d in disku:
		ln1 = len(d["dev"])
		ln2 = len(d["mnt"])
		if (ln1 > f1):
			f1 = ln1
		if (ln2 > f2):
			f2 = ln2
	# build format string
	f1 = f1 + 1
	f2 = f2 + 1
	fstr = "  * {{:{}}} {{:{}}} {{:>11}} {{:>11}} {{:>5.1f}}%".format(f1,f2)
	for d in disku:
		#print("  * {:20} {:24} {:>11} {:>11} {:3.1f}%".format(d["dev"], d["mnt"], size_to_human(d["sz"])[1], size_to_human(d["used"])[1], d["pc"]))
		print(fstr.format(d["dev"], d["mnt"], size_to_human(d["sz"])[1], size_to_human(d["used"])[1], d["pc"]))
	
#### ****************** MQTT support **********************

mqtt_data = { 
	"ts": curr_time, "boot": boot_time, "uptime": up_time, "cput": cpu_t, "vm": v_mem_usage,
	#"vma": v_mem_avail_s,
	"cpu": cpu_usage, "diskp": disks_total_prc, "disku": disks_total_used_s, "diskt": disks_total_size_s }

if (collect_gpu != 0):
	mqtt_data["gput"] = gpu_t

if (mqtt_conf["time_in_unix"] > 0):
	# replace time strings to unix timestamps
	mqtt_data["ts"] = int(curr_time_ts)
	mqtt_data["boot"] = int(boot_time_ts)
	mqtt_data["uptime"] = int(up_time_p)

if (mqtt_conf["disk_human_units"] == 0):
	mqtt_data["disku"]= int(math.floor(disks_total_used/1048576))
	mqtt_data["diskt"]= int(math.floor(disks_total_size/1048576))

if (mqtt_conf["disk_totals"] == 0):
	# disks totals disabled...
	disk_list = {}
	for d in disku:
		#dui = {'dev': part.device, 'mnt': part.mountpoint, 'fs': part.fstype, 'sz': du.total, 'szm': int(math.floor(du.total/1048576)), 'free': du.free, 'freem': int(math.floor(du.free/1048576)), 'used': du.used, 'usedm': int(math.floor(du.used/1048576)), 'pc':du.percent}
		if (mqtt_conf["disk_human_units"] == 0):
			rec = { "total": d["szm"], "used": d["usedm"], "pc": d["pc"] }
		else:
			rec = { "total": size_to_human(d["sz"])[1], "used": size_to_human(d["used"])[1], "pc": d["pc"] }
		disk_list[d["dev"]] = rec
		
	mqtt_data["disks"] = disk_list

# --------- end MQTT data preparations

mqtt_data_json = json.dumps(mqtt_data)
# debug print
#print(mqtt_data_json)
# debug print
#print(mqtt_data)

# if no MQTT enabled, exit script.
if (mqtt_enabled != 1):
	sys.exit()

mc = mqtt.Client()
mc.username_pw_set(mqtt_conf["user"], mqtt_conf["pass"])
mc.connect(mqtt_conf["host"], mqtt_conf["port"], 60)
mc.publish(mqtt_conf["topic"], mqtt_data_json, 0, mqtt_conf["retain"])
mc.disconnect()

#end script.
sys.exit()
