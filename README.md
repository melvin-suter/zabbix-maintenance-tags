# zabbix-maintenance-tag

This script will handle maintenance in zabbix based on tags.

## Installation

Copy the file `maintenance-config.json` to one of these destinations and change the values inside:
- SCRIPT_DIR/maintenance-config.json
- /etc/zabbix/maintenance-config.json
- /etc/zabbix-maintenance/maintenance-config.json

Idealy you'll create a specific user for the script.

Install the dependecies:
```bash
pip3 install -r requirements.txt
```

And create a cron file under `/etc/cron.d/zabbix-maintenance` like this:
```cron
*/5 * * * * root python3 /path/to/script/zabbix-maintenance.py
```

## Usage

**Getting a host in maintenance:**

1. you set the tag `maintenance` to a value like `15m`, `1h`, `3d`
1. if you set the tag `maintenance-nodata`, the data collection will be turned off in the zabbix maintenance window
1. after the script is run, the host will be put inside of a maintenance window
1. after the maintenance window is finished, it will be deleted

**Getting a host out of maintenance early:**

1. delete the tag `maintenance`
1. after the script is run, all `maintenance-*` tags will be deleted and the maintenance window as well

**Extending maintenance:**

1. set the tag `maintenance-extend` and update the `maintenance` tag with the new value
1. after the script runs, the host will be in maintenance for the amount of time specified in `maintenance`
