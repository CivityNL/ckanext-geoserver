# ckanext-geoserver

### Prerequisites

###### Install GDAL
The installation of GDAL is necessary, because gdal has shared libraries and the virtual env prevents python from seeing them. Use this set of commands:

```
sudo apt-add-repository ppa:ubuntugis/ubuntugis-unstable 
sudo apt-get update 
sudo apt-get install libgdal-dev
sudo apt-get build-dep python-imaging
pip install --upgrade pip
pip install Pillow
pip install gsconfig
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
pip install GDAL==1.10.0
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

> Python 2.7.6 (default, Jun 22 2015, 17:58:13) 
> [GCC 4.8.2] on linux2
> Type "help", "copyright", "credits" or "license" for more information.
> >>> 

```

If it is prior 2.7.9 you have to update to a newer version:

```
sudo apt-add-repository ppa:fkrull/deadsnakes-python2.7
sudo apt-get update
sudo apt-get install python2.7 python2.7-dev
```

Additionally,  follow the instructions here [https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning](https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning) and update the ndg-httpsclient to a newer version which can handle https requests:

```
pip install --upgrade ndg-httpsclient
```


### Installation

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
geoserver.rest_url = https://geoserverLogin:geoserverPassword@Geoserver_adress_here/geoserver/rest
geoserver.default_workspace = ckan
geoserver.workspace_name = ckan
geoserver.workspace_uri = http://localhost:5000/ckan #not crucial, can be anything
geoserver.resource_descriptor_only = true #publish/unpublish options only based on existence of resource descriptor
```

Also requires this to be set (should already be set when following the earlier documentation):

```
ckan.datastore.write_url = 'postgresql://ckanuser:pass@localhost/datastore'
```

> **Caution:**
> If your Geoserver and your CKAN run on separate machines it is mandatory to replace occurring `localhost` statements in `/etc/ckan/default/production.ini` with the IP or the DNS name of the CKAN for `ckan.datastore.write_url` and `ckan.datastore.read_url`.   

Add the plugin in `/etc/ckan/default/production.ini`:

```
ckan.plugins = ... geoserver
```

> **Note:**
> Datapusher has to be activated in CKAN config file:
> 
> ```
> ckan.plugins = datapusher ...
> ckan.datapusher.url = http://127.0.0.1:8800/
> ```

Activate the plugin on the server:

```
cd /usr/lib/ckan/default/src/ckanext-geoserver
python setup.py develop
```

Restart the Apache

```
sudo service apache2 restart 
```
## API extension

The action API of CKAN is extended with new endpoints:

* `/api/3/action/geoserver_publish_ogc` to publish a package
* `/api/3/action/geoserver_unpublish_ogc` to unpublish a package

Example in python:

```python
import urllib2
import urllib
import json

request = urllib2.Request('http://YOUT_SERVER/api/3/action/geoserver_publish_ogc')
```

To use this endpoints you have to create a dictionary and provide your API key in an HTTP request. So include it in an Authorization header like in this python code:

```python
request.add_header('Authorization', 'YOUR KEY')
```

The dictionary has to have information about the package which should be published or unpublished [mandatory] and can have information about the keys which should be used when a join over different tables (->resource descriptor) is neccesary. 

Example in python:

```python
dataset_dict = {
	'package_id': 'ID_OF_PACKAGE', # the id of the package for update
	'join_key': 'KEY_FOR_JOIN' # the key if database table joins are neccesary
}
```

The response of this request should claim that everything worked and the package has been published / unpublished

```python
response = urllib2.urlopen(request, data_string)
``` 
