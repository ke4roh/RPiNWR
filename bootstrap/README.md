# Bootstrap for Raspberry Pi

## Startup with Access Point mode

```
% sudo apt-get -y install dnsmasq hostapd apache2
```

### setup Apache web server

#### add directory permission to the /etc/apache2/apache2.conf

```
<Directory /home/pi/RPiNWR/bootstrap/htdocs>
       Options Indexes FollowSymLinks ExecCGI
       AllowOverride All
       Require all granted
</Directory>
```

#### edit /etc/apache2/envvars

```
export APACHE_RUN_USER=pi
export APACHE_RUN_GROUP=pi
```

#### enable cgid

```
# (cd mods-enabled/; ln -s ../mods-available/cgid.* .)

# enable following line in mods-enabled/mime.conf

AddHandler cgi-script .cgi

```
#### change documentroot in sites-enabled/000-default.conf

```
DocumentRoot /home/pi/RPiNWR/bootstrap/htdocs
```

### setup hostapd and network

```
# configset/config/set_config.sh
```

# TODO

- Health check for network connection at boot time
- Once netowork parameter configured, record it to next boot.
- Save location information for data processing
