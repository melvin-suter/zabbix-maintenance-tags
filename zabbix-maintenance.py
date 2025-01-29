import requests
import urllib3
import json
from datetime import datetime, timedelta
import os

# USAGE
# add a tag to a host called "maintenance" with for example "12h"
# optionaly add a tag "maintenance-nodata" if there should not be data collected during the maintenance period
# Run this script in cron every minute and it will automatically create maintenance windows for these hosts and also delete it
# Change these variables:
urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)


#########################
#      Functions
#########################



# Reads config files
def getConfig():
    # Order in which config files should be searched and read if existing
    # The higher up, the more it counts
    possibleFiles = [
        f"{os.path.dirname(os.path.realpath(__file__))}/maintenance-config.json",
        f"/etc/zabbix/maintenance-config.json",
        f"/etc/zabbix-maintenance/maintenance-config.json"
    ]

    for file in possibleFiles:
        if(os.path.exists(file)):
            with open(file) as f:
                config = json.load(f)
                return config
        
    # Exit if no file has been found
    print("NO CONFIG FILE FOUND")
    exit(-1)


def convertTime2Delta(s):
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return int(s[:-1]) * seconds_per_unit[s.lower()[-1]]



#########################
#      API Class
#########################



class API:
    def __init__(self, url, username, password):
        self.url = url
        self.token = False
        self.token = self.post("user.login",{"username": username, "password": password})

    def post(self,method, params):
        if(self.token):
            headers = {'Content-type': 'application/json-rpc', "Authorization": "Bearer %s" % self.token}
        else:
            headers = {'Content-type': 'application/json-rpc'}
        data = {"jsonrpc":"2.0","method":method,"params":params,"id":1}
        r = requests.post(self.url, data=json.dumps(data),verify=False, headers=headers)
        if(r.status_code != 200):
            print("ERROR IN API CALL!")
            exit(1)
        if("result" not in r.json()):
            print("ERROR IN API CALL!")
            print(data)
            print(r)
            print(r.json())
            exit(1)
        return r.json()["result"]





#########################
#      Script/Main
#########################


config = getConfig()
api = API(config["zabbix_url"],config["zabbix_username"] ,config["zabbix_password"])

# go threw all hosts
for host in api.post("host.get",{"output":["hostid","host"],"selectTags":"extend"}):
    currentTags = []
    needsMaintenance = False
    hasMaintenance = False
    maintenanceHandled = False
    maintenanceExtend = False
    maintenanceID = ""
    maintenanceTag = {}
    noData = False

    # check tags
    for tag in host["tags"]:
        currentTags.append({"tag": tag["tag"], "value": tag["value"]})

        # check if maintenance tag is set
        if(tag["tag"] == "maintenance-extend"):
            maintenanceExtend = True


        # check if maintenance tag is set
        if(tag["tag"] == "maintenance"):
            needsMaintenance = True
            maintenanceTag = tag

        # Check if datacollection should be running
        if(tag["tag"] == "maintenance-nodata"):
            noData = True

        # Check if maintenance has already been handled
        if(tag["tag"] == "maintenance-id"):
            maintenanceHandled = True
            maintenanceID = tag["value"]

    # This host has a new maintenance window set
    if(needsMaintenance and not maintenanceHandled):
        # Get Dates
        now = datetime.now()
        end = (datetime.now() + timedelta(seconds=convertTime2Delta(maintenanceTag["value"])))
        period = int((end-now).total_seconds())

        # Add Tags
        currentTags.append({"tag": "maintenance-start", "value": now.strftime("%Y-%m-%d %H:%M:%S")})
        currentTags.append({"tag": "maintenance-end", "value": end.strftime("%Y-%m-%d %H:%M:%S")})

        # Create Maintenance
        data = {"hosts": [{"hostid":host["hostid"]}], "active_since": int(now.timestamp()), "active_till": int(end.timestamp()), "timeperiods": {"period": period, "timeperiod_type": "0"}, "name": "Host Maintenance - %s" % host["host"], "description": "Maintenance created via tag"}
        if(noData):
            data["maintenance_type"] = 1
        else:
            data["maintenance_type"] = 0
        r = api.post("maintenance.create",data)

        currentTags.append({"tag": "maintenance-id", "value": str(r["maintenanceids"][0])})

        # Update Tags
        api.post("host.update",{"hostid": host["hostid"], "tags": currentTags})

    # maintenance tags has been deleted
    if(not needsMaintenance and maintenanceHandled):
        api.post("maintenance.delete", [maintenanceID])

        # Remove all maintenance tags
        tempCurrentTags = currentTags.copy()
        for tag in currentTags:
            if(tag["tag"] in ["maintenance-id","maintenance-start","maintenance-end", "maintenance"]):
                tempCurrentTags.remove(tag)
        currentTags = tempCurrentTags

        # Update Tags
        api.post("host.update",{"hostid": host["hostid"], "tags": currentTags})

    # host's maintenance needs to be extended
    if(maintenanceExtend and maintenanceHandled):
        # Get Dates
        now = datetime.now()
        end = (datetime.now() + timedelta(seconds=convertTime2Delta(maintenanceTag["value"])))
        period = int((end-now).total_seconds())

        # Remove tags
        tempCurrentTags = currentTags.copy()
        for tag in currentTags:
            if(tag["tag"] in ["maintenance-start", "maintenance-end", "maintenance-extend"]):
                tempCurrentTags.remove(tag)
        currentTags = tempCurrentTags

        # re-add tags with correct values
        currentTags.append({"tag": "maintenance-start", "value": now.strftime("%Y-%m-%d %H:%M:%S")})
        currentTags.append({"tag": "maintenance-end", "value": end.strftime("%Y-%m-%d %H:%M:%S")})

        # update Maintenance
        data = {"maintenanceid": maintenanceID, "hosts": [{"hostid":host["hostid"]}], "active_since": int(now.timestamp()), "active_till": int(end.timestamp()), "timeperiods": {"period": period, "timeperiod_type": "0"}, "name": "Host Maintenance - %s" % host["host"], "description": "Maintenance created via tag"}
        if(noData):
            data["maintenance_type"] = 1
        else:
            data["maintenance_type"] = 0
        r = api.post("maintenance.update",data)

        # Update Tags
        api.post("host.update",{"hostid": host["hostid"], "tags": currentTags})


# Clear maintenances that have ended
for maintenance in api.post("maintenance.get",{"output": "extend","selectHosts":"extend"}):
    if(maintenance["description"] == "Maintenance created via tag"):
        now = datetime.now()
        if(int(maintenance["active_till"]) < int(now.timestamp())):
            host = api.post("host.get",{ "output":["hostid","host"],"selectTags":"extend",  "hostids":[maintenance["hosts"][0]["hostid"]]})[0]
            tags = []
            # Remove all maintenance tags
            for tag in host["tags"]:
                if(tag["tag"] not in  ["maintenance-id","maintenance-start","maintenance-end", "maintenance"]):
                    tags.append({"tag": tag["tag"], "value": tag["value"]})

            # Update Tags
            api.post("host.update",{"hostid": host["hostid"], "tags": tags})

            api.post("maintenance.delete", [maintenance["maintenanceid"]])
