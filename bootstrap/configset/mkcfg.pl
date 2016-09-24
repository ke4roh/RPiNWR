#! /usr/bin/env perl
use File::Basename;
$mypath = dirname($0);
%db = ();
if (open(JSON,"$mypath/../htdocs/network.json")) {
    while (<JSON>) {
	s/[\r\n]//;
	s/,$//;
	my ($k,@vs) = split(/[\:]/,$_);
	$v = join(":",@vs);
	$k =~ s/^\"//;
	$k =~ s/\"$//;
	$v =~ s/^\"//;
	$v =~ s/\"$//;
	$db{$k} = $v;
    }
}

#
# wpa_supplicant
#
if (($db{"ssid"} ne "") && (length($db{"passphrase"}) >= 6)) {

    $fn = "$mypath/config/wifi_client/etc/wpa_supplicant/wpa_supplicant.conf";
    open(F,">",$fn) || die $!;
    print F << "+++";
country=JP
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
+++
;
    close(F);
    system("wpa_passphrase $db{'ssid'} $db{'passphrase'} >> $fn");
}

#
# dhcpcd.conf
#
$fn = "$mypath/config/wifi_client/etc/dhcpcd.conf";
if (open(F,"<",$fn)){
    $buf = "";
    while (<F>){
	$buf .= $_;
	last if (/# AUTOMATIC CONFIGURATION BELOW/);
    }
    close(F);

    if (($db{"addrtype"} eq "manual") && ($db{"ipaddr"} ne "")) {
	$buf .= << "+++";
interface wlan0
static ip_address=$db{ipaddr}/24
static routers=$db{gateway}
+++
	;
    }
    open(F,">",$fn) || die $!;
    print F $buf;
    close(F);
}

#
# proxy
#
if ($db{"proxy"} ne "") {
    open(F,">", "$mypath/../../proxy.py");
    print F << "+++";
proxies = {
  "http":"$db{'proxy'}",
}
+++
    ;
    close(F);
}
else {
    unlink("$mypath/../../proxy.py");
}
