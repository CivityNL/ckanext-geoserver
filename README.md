### Geoserver

#### Prerequisites

###### Install GDAL
The installation of GDAL is necessary, because gdal has shared libraries and the virtual env prevents python from seeing them. Use this set of commands:

```
sudo apt-add-repository ppa:ubuntugis/ubuntugis-unstable 
sudo apt-get update 
sudo apt-get install libgdal-dev
sudo apt-get build-dep python-imaging
pip install Pillow
pip install gsconfig
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
pip install GDAL==1.10.0
pip install usginmodels
```

###### Install PostGIS for datastore database
It is mandatory to have the PostGIS extension installed and activated on the datastore database. For example, if you are working on an Ubuntu machine:

```
# install PostGIS
sudo apt-get update
sudo apt-get install postgis
# login as superuser in postgres 
su - postgres
# connect to the datastore database
psql datastore_default
# install extension
datastore_default=# CREATE EXTENSION postgis;
```

###### (optional) Install SSL compatible Python Version
If your Server does have SSL enabled and if you are working on an Ubuntu 14.04 LTS or prior system: by default version 2.7.6 of Python is installed. Due to SSL fixes ist is mandatory to update to a version 2.7.9+. Check which version is installed: 

```
python 

> Python 2.7.6 (default, Dec 15 2015, 16:46:19)  
> [GCC 4.8.4] on linux2
> Type "help", "copyright", "credits" or "license" for more information.
>>>> 

```

If it is prior 2.7.9 you have to update to a newer version:

```
sudo apt-add-repository ppa:fkrull/deadsnakes-python2.7
sudo apt-get update
sudo apt-get install python2.7 python2.7-dev
```

#### Installation

After that install the Geoserver extension. We use the forked extension from original https://github.com/ngds/ckanext-geoserver,  as fixed some bugs and decoupled it from other ngds requirements.   

```
cd /usr/lib/ckan/default/src/ckan
. /usr/lib/ckan/default/bin/activate

cd /usr/lib/ckan/default/src
git clone https://github.com/GeoinformationSystems/ckanext-geoserver.git
cd ckanext-geoserver/
pip install -r requirements.txt
```

After installation completes, edit `/etc/ckan/default/production.ini` with the following custom configurations:

```
geoserver.rest_url = geoserver://admin:geoserver@Server_adress_here:8080/geoserver/rest
geoserver.default_workspace = ckan
geoserver.workspace_name = ckan
geoserver.workspace_uri = http://localhost:5000/ckan #not crucial, can be anything
```

Also requires this to be set (should already be set when following the earlier documentation):

```
ckan.datastore.write_url = 'postgresql://ckanuser:pass@localhost/datastore'
```

> **Caution:**
> If your Geoserver and your CKAN run on separate machines it is mandatory to replace occurring `localhost` statements in `/etc/ckan/default/production.ini` with the IP or the DNS name of the CKAN for `ckan.datastore.write_url` and `ckan.datastore.read_url`.   

Activate the plugin on the server:

```
cd /usr/lib/ckan/default/src/ckanext-geoserver
python setup.py develop
```

Add the plugin in `/etc/ckan/default/production.ini`:

```
ckan.plugins = geoserver ...
```

> **Note:**
> Datapusher has to be activated in CKAN config file:
> 
> ```
> ckan.plugins = datapusher ...
> ckan.datapusher.url = http://127.0.0.1:8800/
> ```

It could be possible, that the deployment with datapusher into the database fails. If the following errors occur in the log files (e.g. `/var/log/apache2/ckan_default.error.log`):

```
/usr/lib/ckan/default/lib/python2.7/site-packages/requests/packages/urllib3/util/ssl_.py:90: InsecurePlatformWarning: A true SSLContext object is not available. This prevents urllib3 from configuring SSL appropriately and may cause certain SSL connections to fail. For more information, see https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning.

```

Then, please follow the instructions here [https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning](https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning) and update the ndg-httpsclient to a newer version which can handle https requests:

```
pip install --upgrade ndg-httpsclient
```


#### Geoserver publishing (automated)

This extension contains two paster commands that can be used in conjunction with crontab & supervisor to automatically publish tier 3 data to NGDS services (Geoserver)

* `paster geoserver publish-ogc-redis-queue`: this command will run a sql query against the database and return all eligible datasets (dataset package extra key `md_package` has to include `NGDS Tier 3 Data, csv format:` as its package extra value & it also must be tagged with a keyword that contains `usgincm:`) that can be published to ogc (geoserver). The ids of these datasets will be added to a redis queue (the name of the queue = `publish_ogc_queue` (info on redis queues and operations that can be performed on them can be found @ [http://redis.io](http://redis.io))) We run this everything 15 minutes through a cronjob (See: [https://github.com/ngds/install-and-run/blob/master/rpm_install/etc/cron.d/ckan-harvest](https://github.com/ngds/install-and-run/blob/master/rpm_install/etc/cron.d/ckan-harvest))

* `paster geoserver publish-ogc-worker`: This command will start a worker that runs in the background. It will pop dataset ids from the redis queue and publish them to ogc (geoserver). Worker processes can be managed through supervisor (see: [https://github.com/ngds/install-and-run/blob/master/rpm_install/etc/supervisord.conf](https://github.com/ngds/install-and-run/blob/master/rpm_install/etc/supervisord.conf))

##### Possible ogc publishing errors:

* `PUBLISH_OGC: Error Connecting to Redis while building publish_ogc_queue`: check redis connection paramenters in `production.ini`. Also make sure that the redis server is up and running.
* `PUBLISH_OGC_QUEUE: There was en ERROR while pushing ids to publish_ogc_queue`: this means that `publish-ogs-redis-queue` was not able to add dataset ids to the redis queue. Check to see if the redis server is working as expected.
* `PUBLISH_OGC_WORKER: ERROR, could not connect to Redis`: the worker was not able to connect to the redis server. Make sure the redis server is up and running.
* `PUBLISH_OGC_WORKER: An Error has occured while publishing dataset`: this means that ckan threw an exception while publishing dataset ids to the redis queue. See what the exception says and go from there (most often it is an issue with ckan not bening able to reach the redis server.
* `PUBLISH_OGC: ERROR, Could not get required API CALL parameters for dataset '`: this means that ckan doesn't have the necessary data to call the geoserver api (which publishes tier 3 data to ogc). See what data is missing and troubleshoot from there.