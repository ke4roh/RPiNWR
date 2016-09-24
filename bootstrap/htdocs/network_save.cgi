#! /usr/bin/env perl
use File::Basename;
$mypath = dirname($0);
use CGI;
$q = new CGI;
$p = $q->Vars;

$ifcfg = `ifconfig eth0`;
if ($ifcfg =~ /HWaddr ([0-9a-f:]+)/) {
    @w = split(/:/,$1);
    $x3 = hex($w[3]);
    $x4 = hex($w[4]);
    $x5 = hex($w[5]);
    $sn = $x3 * 65536 + $x4 + 256 + $x5;
}
if (open(F,">$mypath/../lightning/id.py")) {
    print F qq(serial_number = "$sn"\n);
    close(F);
}

if (($p->{'ssid'} ne "") || ($ARGV[0] eq "init")) {
    if (open(JSON,">$mypath/network.json")) {
	print JSON << "+++";
{
"serial":"$sn",
"ssid":"$p->{'ssid'}",
"passphrase":"$p->{'passphrase'}",
"addrtype":"$p->{'addrtype'}",
"ipaddr":"$p->{'ipaddr'}",
"netmask":"$p->{'netmask'}",
"gateway":"$p->{'gateway'}",
"proxy":"$p->{'proxy'}"
}
+++
	;
close(JSON);
    }
}


print $q->header(-content_type => "application/json");
if ($p->{'ssid'} ne "") {
    system("perl $mypath/../piset/mkcfg.pl");
    system("sudo $mypath/../piset/config/set_config.sh wifi_client");
    print qq({"stat":"OK"});
}
else {
    print qq({"stat":"none"});
}
