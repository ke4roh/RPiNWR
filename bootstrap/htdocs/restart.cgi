#! /usr/bin/env perl
use CGI;
$q = new CGI;
print $q->header(-status => 204);
system("sudo reboot");
