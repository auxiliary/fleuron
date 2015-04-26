#!/usr/bin/env python

"""
    Fleuron ver 0.2 - A silent flash drive copier.
    Copyright (C) 2012  Mohammad A.Raji <moh@nuinet.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import time
import os, sys
import Queue
import shutil
import random
import logging
import dbus
import gobject
from dbus.mainloop.glib import DBusGMainLoop


MOUNT_TIMEOUT = 5 #Seconds
FILE_SIZE_LIMIT = 30 * 1024 * 1024 #Bytes
RANDOM_WAITING_MIN = 2 #Seconds
RANDOM_WAITING_MAX = 9 #Seconds
PROBABILITY_OF_WAITING = 30 #Percentage
LOG_FILENAME = "fleuron_log.log"
LOG_FILE_MAX_SIZE = 50 * 1024 #Bytes
BLACKLIST_FILENAME = "fleuron_blacklist"
VERSION = 0.2

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
proxy = bus.get_object("org.freedesktop.UDisks", "/org/freedesktop/UDisks")
iface = dbus.Interface(proxy, "org.freedesktop.UDisks")

Q = Queue.Queue()

def get_dev_info(dev_path):
    for dev in iface.EnumerateDevices():
        if dev_path == dev:
            device = bus.get_object("org.freedesktop.UDisks", dev);
            device_info = dbus.Interface(device, dbus.PROPERTIES_IFACE)
            return device_info
        
def device_added_callback(dev_path):
    if os.stat(LOG_FILENAME).st_size > LOG_FILE_MAX_SIZE:
        clear_logs()

    dev_info = get_dev_info(dev_path)
    is_mounted  = dev_info.Get("org.freedesktop.UDisks.Device", "DeviceIsMounted")
    timeout = MOUNT_TIMEOUT
    while is_mounted == False and timeout > 0:
        time.sleep(0.5)
        is_mounted  = dev_info.Get("org.freedesktop.UDisks.Device", "DeviceIsMounted")
        timeout-=1
        
    mount_points = dev_info.Get("org.freedesktop.UDisks.Device", "DeviceMountPaths")
    mount_point = ""
    if len(mount_points) > 0:
        mount_point = mount_points[0]

        log.info('Added ' + dev_path)
        log.info('Mounted at  ' + mount_point)
        
        device_uuid = dev_info.Get("org.freedesktop.UDisks.Device", "IdUuid").lower()
        device_label = dev_info.Get("org.freedesktop.UDisks.Device", "IdLabel").lower()
        blacklist=""
        
        if os.path.exists(BLACKLIST_FILENAME):
            with open(BLACKLIST_FILENAME) as blacklist_fh:
                blacklist = blacklist_fh.readlines()
        for entry in blacklist:
            if entry.startswith('#'):
                continue
            entry = entry.strip().lower()
            if (entry == device_uuid) or (entry == device_label):
                log.info("Device is blacklisted.")
                return -1
        
        copy(mount_point)
    
def device_removed_callback(dev_path):
    log.warning('Removed ' + dev_path)
    Q.queue.clear()

def device_changed_callback(dev_path):
    pass

def sorted_listdir(path):
    return sorted(os.listdir(path))
    
def random_wait():
    rand = random.Random()
    wait_probability = rand.randint(1, 100)
    if(wait_probability > PROBABILITY_OF_WAITING):
        return 0
    wait_time = rand.randint(RANDOM_WAITING_MIN, RANDOM_WAITING_MAX)
    log.info('Waiting for ' + str(wait_time) + ' seconds...')
    time.sleep(wait_time)
    return wait_time
    
def copy(src_path, dest_path=os.curdir):
    for dir in sorted_listdir(src_path):
        full_dir_path = src_path + "/" + dir
        if os.path.isdir(full_dir_path):
            Q.put(full_dir_path)
        else:#Then it's a file
            copy_file(full_dir_path, dest_path)
    
    copied = True
    while(Q.empty() == False):
        if copied:
            waited = random_wait() > 0
        else:
            waited = 0
        root = Q.get()
        if waited:
            if os.path.exists(root) == False:
                return
        for dir in sorted_listdir(root):
            full_dir_path = root + "/" + dir
            if os.path.isdir(full_dir_path):
                Q.put(full_dir_path)
            else:
                copied = copy_file(full_dir_path, dest_path)
    
def copy_file(full_file_path, dest_path=os.curdir):
    if os.stat(full_file_path).st_size > FILE_SIZE_LIMIT:
        return
    file_path = full_file_path[0:full_file_path.rfind("/")]
    file_path = file_path[1:]#To ommit the first slash so that the path does not start with a slash
    file_name = full_file_path[full_file_path.rfind("/"):]
    if os.path.exists("./" + file_path) == False:
        os.makedirs(file_path)
    if os.path.exists("./" + file_path + "/" + file_name) == False:
        shutil.copy2(full_file_path, "./" + file_path)
        log.info("Copying file " + full_file_path[:50] + "...")
        return True
    else:
        return False

def clear_logs():
    with open(LOG_FILENAME, 'w'):
        pass
    
if __name__ == '__main__':
    cur = os.path.realpath(__file__)
    cur = cur[:cur.rfind("/")]
    os.chdir(cur)
    
    log = logging.getLogger()
    ch = logging.StreamHandler()
    fh = logging.FileHandler(LOG_FILENAME)
    log.addHandler(ch)
    log.addHandler(fh)
    ch_fmt = logging.Formatter("%(levelname)s\t: %(message)s")
    fh_fmt = logging.Formatter("%(asctime)s %(levelname)s\t: %(message)s")
    ch.setFormatter(ch_fmt)
    fh.setFormatter(fh_fmt)
    log.setLevel(logging.INFO)
    
    iface.connect_to_signal("DeviceAdded", device_added_callback)
    iface.connect_to_signal("DeviceRemoved", device_removed_callback)
    iface.connect_to_signal("DeviceChanged", device_changed_callback)
    
    print "Fleuron", VERSION
    log.info("Session started.")
    
    mainloop = gobject.MainLoop()
    mainloop.run()
    
