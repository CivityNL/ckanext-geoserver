# ckanext-geoserver

### Prerequisites

##### Install GDAL
The installation of GDAL is necessary, because gdal has shared libraries and the virtual env prevents python from seeing them. Use this set of commands:

```bash
sudo apt-add-repository ppa:ubuntugis/ubuntugis-unstable
sudo apt-get update
sudo apt-get install libgdal-dev
sudo apt-get build-dep python-imaging
sudo pip install --upgrade pip
sudo pip install Pillow
sudo pip install gsconfig
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
sudo pip install GDAL==1.10.0
```

##### Install PostGIS for datastore database
It is mandatory to have the PostGIS extension installed and activated on the datastore database. For example, if you are working on an Ubuntu machine:

```bash
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
or on Debian 8:

```bash
sudo -u postgres psql -d datastore_default -c 'CREATE EXTENSION postgis;'
```

##### (optional) Install SSL compatible Python Version
If your Server does have SSL enabled and if you are working on an Ubuntu 14.04 LTS or prior system: by default version 2.7.6 of Python is installed. Due to SSL fixes ist is mandatory to update to a version 2.7.9+. Check which version is installed:

```python
> Python 2.7.6 (default, Jun 22 2015, 17:58:13)
> [GCC 4.8.2] on linux2
> Type "help", "copyright", "credits" or "license" for more information.
> >>>
```

If it is prior 2.7.9 you have to update to a newer version:

```bash
sudo apt-add-repository ppa:fkrull/deadsnakes-python2.7
sudo apt-get update
sudo apt-get install python2.7 python2.7-dev
```

>The new python installation has to be activate in CKAN's virtual environment:

>```bash
cd /usr/lib/ckan/default/src/ckan
. /usr/lib/ckan/default/bin/activate
sudo virtualenv --no-site-packages /usr/lib/ckan/default
```

> **Note:**
> 
> If an error occurs like the following:

> ```bash
> The program 'virtualenv' is currently not installed.
> ```

>then install with the following command:

>```bash
>sudo apt-get install python-virtualenv
>```

Additionally,  follow the instructions here [https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning](https://urllib3.readthedocs.org/en/latest/security.html#insecureplatformwarning) and update the ndg-httpsclient to a newer version which can handle https requests:

```bash
pip install --upgrade ndg-httpsclient
```

##### Install GeoserverService
For the raster publishing process it is mandatory to copy the files in the filesystem of the Geoserver. Since this is not possible within the web-environment and Geoserver itself do not provides such a function, you have to populate the project https://github.com/GeoinformationSystems/GeoserverService into the Geoserver. 

Additionally, it is necessary to create a file storage on the CKAN machine with full write access. For this, please use the following commands:

```bash
sudo mkdir /var/tmp/GeoserverUpload
chmod 777 -R /var/tmp/GeoserverUpload
```

To tell CKAN where to find the GeoserverService extension, you have to edit `/etc/ckan/default/production.ini` and add the following line (updated to your needs):

```ini
geoserver.upload_service = http://your_server_location/GeoserverService/upload/
```

This plugin has a basic authorization machanism included. To authorize yourself as a valid user, please edit the `web.xml` of the GeoserverUpload webapp in the tomcat folder:

```xml
<context-param>
	<!-- basic authenticatio I, allows only valid ip Adresses -->
	<param-name>AllowedIPRange</param-name>
	<param-value>141.(30|76).*</param-value>
</context-param>
<context-param>
	<!-- define the folder where temporary files are stored -->
	<param-name>SavePath</param-name>
	<param-value>/var/tmp/GeoserverUpload/</param-value>
</context-param>
<context-param>
	<!-- basic authentication II, whoever uses this key can use this appliction -->
	<param-name>SecretKey</param-name>
	<param-value><!-- YourSecretPassphrase --></param-value>
</context-param>
```
 
If you use the second methos, than you have to edit the following line to `/etc/ckan/default/production.ini` (match passphrases):

```ini
geoserver.upload_key = YourSecretPassphrase
```
 

### Installation

After that install the Geoserver extension. We use the forked extension from original https://github.com/ngds/ckanext-geoserver, fixed some bugs and decoupled it from other ngds requirements.

```bash
cd /usr/lib/ckan/default/src/ckan
. /usr/lib/ckan/default/bin/activate

cd /usr/lib/ckan/default
pip install -e 'git+https://github.com/GeoinformationSystems/ckanext-geoserver.git#egg=ckanext-geoserver'
cd src/ckanext-geoserver/
pip install -r requirements.txt
```

> If an error simmilar to the following occurs:

>```error
>Command "/usr/lib/ckan/default/bin/python -c "import setuptools, tokenize;__file__='/tmp/pip-build-nEO9Nd/gdal/
>setup.py';exec(compile(getattr(tokenize, 'open', open)(__file__).read().replace('\r\n', '\n'), __file__, 'exec'))" install
> --record /tmp/pip-d_mpqx-record/install-record.txt --single-version-externally-managed --compile --install
> -headers /usr/lib/ckan/default/include/site/python2.7/gdal" 
> failed with error code 1 in /tmp/pip-build-nEO9Nd/gdal
>```
> please update the `setuptools`:

>```bash 
sudo pip install -U setuptools
```

After installation completes, edit `/etc/ckan/default/production.ini` with the following custom configurations:

```ini
geoserver.rest_url = https://geoserverLogin:geoserverPassword@Geoserver_adress_here/geoserver/rest
geoserver.default_workspace = ckan
geoserver.workspace_name = ckan
# not crucial, can be anything
geoserver.workspace_uri = http://localhost:5000/ckan
# default: true -  publish/unpublish options only based on existence of resource 
geoserver.descriptor_only = true
# default: schema_descriptor - the name for the schema_descriptor
geoserver.descriptor_name = schema_descriptor
# add this to allow package_search API functionality also on parent_resource field
ckan.extra_resource_fields = parent_resource
```

Also requires this to be set (should already be set when following the earlier documentation):

```ini
ckan.datastore.write_url = 'postgresql://ckanuser:pass@localhost/datastore'
ckan.storage.directory = /var/tmp/
```


> **Caution:**
> If your Geoserver and your CKAN run on separate machines it is mandatory to replace occurring `localhost` statements in `/etc/ckan/default/production.ini` with the IP or the DNS name of the CKAN for `ckan.datastore.write_url` and `ckan.datastore.read_url`.   

Add the plugin in `/etc/ckan/default/production.ini`:

```ini
ckan.plugins = ... geoserver
```

> **Note:**
> Datapusher has to be activated in CKAN config file:
>
> ```ini
> ckan.plugins = datapusher ...
> ckan.datapusher.url = http://127.0.0.1:8800/
> ```

Activate the plugin on the server:

```bash
cd /usr/lib/ckan/default/src/ckanext-geoserver
python setup.py develop
```

Give writing permissions to the `/var/tmp/` folder:
 
```bash
sudo chmod 777 -R /var/tmp
```

Restart the Apache

```bash
sudo service apache2 restart
```

If your dataset is now qualified (schema descriptor or shape file(s)) and you have the permission to edit this dataset, then you should see a `Publish/Unpublish OGC` button next to your dataset name in the dataset detail page.

![ckanext-geoserver publish button on detailed side](/Users/danielhenzen/Documents/Projekte/COLABIS/CKAN/documentation/pictures/ckanext-geoserver_publish_button.png)

## API extension

Please follow the API guide of CKAN at http://docs.ckan.org/en/latest/api/index.html to get a common understanding of the capabilities and the workflow of how to use CKANs included API.

### Extended API Reference

* `ckan.logic.action.geoserver_publish_ogc(context, data_dict)`

	Publish a qualified dataset as OGC complied service on a geoserver.
	The user must have permission to 'edit' the dataset. Return `True` if the publishing process was successful and `False` otherwise.
	
	**Parameter:**
	* **package_id** (*string*) - the id of the package for publish
	* **join_key** (*string*) - the key if database table joins are necessary

	**Return type:** boolean
	
* `ckan.logic.action.geoserver_unpublish_ogc(context, data_dict)`	
	Unpublish a already published dataset from geoserver.
	The user must have permission to 'edit' the dataset. Return `True` if the unpublishing process was successful and `False` otherwise.
	
	**Parameter:**
	* **package_id** (*string*) - the id of the package for unpublish

	**Return type:** boolean

### Application Example

The action API of CKAN is extended with new endpoints:

* `/api/3/action/geoserver_publish_ogc` to publish a package
* `/api/3/action/geoserver_unpublish_ogc` to unpublish a package


Example in python:

```python
import urllib2
import urllib
import json

request = urllib2.Request('http://YOUR_SERVER/api/3/action/geoserver_publish_ogc')
```

To use this endpoints you have to create a dictionary and provide your API key in an HTTP request. So include it in an Authorization header like in this python code:

```python
request.add_header('Authorization', 'YOUR KEY')
```

The dictionary has to have information about the package which should be published or unpublished [mandatory] and can have information about the keys which should be used when a join over different tables is necessary.

Example in python:

```python
dataset_dict = {
	'package_id': 'ID_OF_PACKAGE', # the id of the package for update
	'join_key': 'KEY_FOR_JOIN' # the key if database table joins are necessary
}
```

The response of this request should claim that everything worked and the package has been published / unpublished

```python
data_string = urllib.quote(json.dumps(dataset_dict))
response = urllib2.urlopen(request, data_string)
```
