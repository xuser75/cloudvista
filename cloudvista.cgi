#!/usr/bin/perl
##############################################################
# CloudVista  —  cloud storage manager
# Copyright © RoyR 2026 All rights reserved.
# Distributed under the terms of the MIT License.
#
# perl 5.8+, core modules + CGI
# chmod 755, set $STORAGE_ROOT below
##############################################################

use strict;
use warnings;
use CGI ();
use CGI::Cookie;
use Digest::MD5 qw(md5_hex);
use File::Basename qw(basename);
use POSIX qw(strftime);

$| = 1; # unbuffered — never silently drop bytes

##############################################################
# CONFIGURATION
##############################################################
# Note: STORAGE_ROOT should not be in the document root, unless
# you know what you are doing.
my $STORAGE_ROOT = "/var/www/storage"; # must be writable by httpd user
my $MAX_UPLOAD   = 1073741824;         # 1 GB
my $SCRIPT_NAME  = $ENV{SCRIPT_NAME} || "/cgi-bin/cloudvista.cgi";
my $COOKIE_DAYS  = 30;
##############################################################

$CGI::POST_MAX        = $MAX_UPLOAD;
$CGI::DISABLE_UPLOADS = 0;
# ---- bail out loud if storage root is missing ----
unless (-d $STORAGE_ROOT) {
    print "Content-Type: text/plain\r\n\r\n";
    print "ERROR: \$STORAGE_ROOT ($STORAGE_ROOT) does not exist.\n";
    print "Fix:   mkdir -p $STORAGE_ROOT && chown <httpd-user> $STORAGE_ROOT\n";
    exit;
}

my $q      = CGI->new;
my $action = $q->param('action') || '';
# ---- read cookies ----
my %cookies = CGI::Cookie->fetch;
my $c_uhash = $cookies{uhash} ? $cookies{uhash}->value : '';
my $c_phash = $cookies{phash} ? $cookies{phash}->value : '';

##############################################################
# HEADER HELPERS  — raw prints, no CGI.pm header()/redirect()
##############################################################

sub send_redirect {
    my ($url, @cookies) = @_;
    print "Location: $url\r\n";
    for my $c (@cookies) { print "Set-Cookie: ", $c->as_string, "\r\n";
    }
    print "\r\n";
    exit;
}

sub send_page_header {
    my @cookies = @_;
    print "Content-Type: text/html; charset=UTF-8\r\n";
    for my $c (@cookies) { print "Set-Cookie: ", $c->as_string, "\r\n"; }
    print "\r\n";
}

sub make_login_cookies {
    my ($uh, $ph) = @_;
    my $exp = "+${COOKIE_DAYS}d";
    return (
        CGI::Cookie->new(-name=>'uhash',-value=>$uh,-expires=>$exp,-path=>'/',-httponly=>1),
        CGI::Cookie->new(-name=>'phash',-value=>$ph,-expires=>$exp,-path=>'/',-httponly=>1),
    );
}

sub make_expired_cookies {
    return (
        CGI::Cookie->new(-name=>'uhash',-value=>'',-expires=>'-1d',-path=>'/',-httponly=>1),
        CGI::Cookie->new(-name=>'phash',-value=>'',-expires=>'-1d',-path=>'/',-httponly=>1),
    );
}

##############################################################
# MISC HELPERS
##############################################################

sub fmt_size {
    my $b = shift || 0;
    return sprintf("%.1f GB", $b/1073741824) if $b >= 1073741824;
    return sprintf("%.1f MB", $b/1048576)    if $b >= 1048576;
    return sprintf("%.1f KB", $b/1024)       if $b >= 1024;
    return "$b B";
}

sub dir_size {
    my $dir = shift;
    my $tot = 0;
    if (opendir my $dh, $dir) {
        while (my $f = readdir $dh) {
            next if $f eq '.'
|| $f eq '..';
            $tot += (stat "$dir/$f")[7]||0 if -f "$dir/$f";
        }
        closedir $dh;
    }
    return $tot;
}

sub safe_name {
    my $n = basename(shift || '');
    $n =~ s/[^\w.\-]/_/g;
    $n =~ s/^\./dot_/;
    $n =~ s!/!_!g;
    return length($n) ? $n : 'file';
}

sub validate_session {
    my ($uh, $ph) = @_;
    return undef unless $uh =~ /^[0-9a-f]{32}$/ && $ph =~ /^[0-9a-f]{32}$/;
    my $dir = "$STORAGE_ROOT/$uh/$ph";
    return -d $dir ?
$dir : undef;
}

sub esc {
    my $s = shift || '';
    $s =~ s/&/&amp;/g;
    $s =~ s/</&lt;/g;
    $s =~ s/>/&gt;/g;
    $s =~ s/"/&quot;/g;
    return $s;
}

##############################################################
# HTML CHROME
##############################################################

my $CSS = <<'CSS';
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--accent:#58a6ff;
  --green:#3fb950;--red:#f85149;--text:#c9d1d9;--muted:#8b949e;
  --r:6px;--mono:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--bg);color:var(--text);font-family:var(--mono);
  font-size:14px;min-height:100vh}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.shell{max-width:860px;margin:0 auto;padding:24px 16px 48px}
.topbar{display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--border);padding-bottom:14px;margin-bottom:24px}
.topbar .logo{font-size:18px;font-weight:700;color:var(--accent);letter-spacing:1px}
.topbar .logo span{color:var(--muted);font-weight:400}
.topbar .nav a{margin-left:18px;color:var(--muted);font-size:13px}
.topbar .nav a:hover{color:var(--text)}
.card{background:var(--panel);border:1px solid var(--border);
border-radius:var(--r);padding:24px 28px;margin-bottom:20px}
.card h2{font-size:14px;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:18px;padding-bottom:10px;
  border-bottom:1px solid var(--border)}
label{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;
  letter-spacing:.8px;margin-bottom:5px;margin-top:14px}
input[type=text],input[type=password]{width:100%;background:var(--bg);
  border:1px solid var(--border);border-radius:var(--r);color:var(--text);
  font-family:var(--mono);font-size:14px;padding:8px 12px;outline:none}
input[type=text]:focus,input[type=password]:focus{border-color:var(--accent)}
input[type=file]{width:100%;background:var(--bg);border:1px dashed var(--border);
  border-radius:var(--r);color:var(--muted);font-family:var(--mono);
  font-size:13px;padding:10px 12px;cursor:pointer}
input[type=file]:hover{border-color:var(--accent)}
.btn{display:inline-block;margin-top:16px;padding:8px 20px;border-radius:var(--r);
border:none;font-family:var(--mono);font-size:13px;font-weight:600;cursor:pointer}
.btn:hover{opacity:.82}
.btn-primary{background:var(--accent);color:#0d1117}
.btn-success{background:var(--green);color:#0d1117}
table{width:100%;border-collapse:collapse}
thead tr{border-bottom:2px solid var(--border)}
th{text-align:left;color:var(--muted);font-size:11px;text-transform:uppercase;
  letter-spacing:.8px;padding:0 8px 10px}
td{padding:9px 8px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(88,166,255,.04)}
.fname{color:var(--text);font-size:13px;word-break:break-all}
.fsize,.fdate{color:var(--muted);white-space:nowrap}
.fdate{font-size:12px}
.factions{white-space:nowrap;text-align:right}
.factions a{margin-left:12px;font-size:12px}
.dl{color:var(--accent)}.del{color:var(--red)}
.alert{border-radius:var(--r);padding:10px 16px;margin-bottom:18px;
  font-size:13px;border-left:3px solid}
.alert-err{background:rgba(248,81,73,.1);border-color:var(--red);color:var(--red)}
.alert-ok{background:rgba(63,185,80,.1);border-color:var(--green);color:var(--green)}
.bar-bg{background:var(--border);border-radius:3px;height:6px;
  margin-top:8px;overflow:hidden}
.bar-fg{height:100%;border-radius:3px;background:var(--accent)}
.usage{font-size:12px;color:var(--muted);margin-top:5px}
.login-wrap{display:flex;align-items:center;justify-content:center;min-height:90vh}
.login-box{width:100%;max-width:380px}
.logo-big{text-align:center;font-size:26px;font-weight:700;color:var(--accent);
margin-bottom:28px;letter-spacing:2px}
.logo-big span{color:var(--muted);font-weight:400}
.tabs{display:flex;border-bottom:1px solid var(--border);margin-bottom:20px}
.tab{padding:8px 20px;font-size:13px;color:var(--muted);
  border-bottom:2px solid transparent;margin-bottom:-1px;text-decoration:none}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.empty{text-align:center;padding:40px 0;color:var(--muted);font-size:13px}
footer{margin-top:40px;text-align:center;color:var(--muted);font-size:11px}
CSS

sub html_open {
    my $t = esc(shift || 'CloudVista');
    return "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
         .
"<meta charset=\"UTF-8\">\n"
         .
"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
         .
"<title>$t</title>\n"
         . "<style>$CSS</style>\n"
         .
"</head>\n<body>\n";
}

sub html_close {
    return "<footer>CloudVista © 2026 RoyR</footer>\n</body>\n</html>\n";
}

##############################################################
# ROUTING
##############################################################

# ---- DOWNLOAD (raw binary response, must come first) ----
if ($action eq 'download') {
    my $ud   = validate_session($c_uhash, $c_phash);
    my $file = safe_name($q->param('file') || '');
    my $path = ($ud && $file) ? "$ud/$file" : '';
    unless ($path && -f $path) {
        send_redirect($SCRIPT_NAME);
    }

    my $size = (stat $path)[7];
    (my $disp = $file) =~ s/[^\w.\-]/_/g;

    binmode STDOUT;
    print "Content-Type: application/octet-stream\r\n";
    print "Content-Length: $size\r\n";
    print "Content-Disposition: attachment; filename=\"$disp\"\r\n";
    print "\r\n";
    open my $fh, '<', $path or exit;
    binmode $fh;
    my $buf;
    print $buf while read $fh, $buf, 65536;
    close $fh;
    exit;
}

# ---- LOGOUT ----
if ($action eq 'logout') {
    send_redirect($SCRIPT_NAME, make_expired_cookies());
}

# ---- LOGIN ----
if ($action eq 'login') {
    my $user = $q->param('username') || '';
    my $pass = $q->param('password') || '';

    if ($user ne '' && $pass ne '') {
        my $uh = md5_hex($user);
        my $ph = md5_hex($pass);
        if (-d "$STORAGE_ROOT/$uh/$ph") {
            send_redirect($SCRIPT_NAME, make_login_cookies($uh, $ph));
        }
    }
    send_page_header();
    print html_open("CloudVista");
    print_login_form('invalid credentials.', 'login');
    print html_close();
    exit;
}

# ---- REGISTER ----
if ($action eq 'register') {
    my $user    = $q->param('username') || '';
    my $pass    = $q->param('password') || '';
    my $confirm = $q->param('confirm')  || '';
    my $err     = '';

    if    ($user eq '' || $pass eq '') { $err = 'all fields required.';
    }
    elsif (length($user) < 2)          { $err = 'username min 2 chars.';
    }
    elsif (length($pass) < 4)          { $err = 'password min 4 chars.';
    }
    elsif ($pass ne $confirm)          { $err = 'passwords do not match.';
    }
    else {
        my $uh   = md5_hex($user);
        my $ph   = md5_hex($pass);
        my $udir = "$STORAGE_ROOT/$uh";
        my $pdir = "$udir/$ph";
        if    (-d $udir)              { $err = 'username already taken.';
        }
        elsif (!mkdir $udir, 0750)    { $err = 'server error (mkdir).';
        }
        elsif (!mkdir $pdir, 0750)    { $err = 'server error (mkdir).';
        }
        else {
            send_redirect($SCRIPT_NAME, make_login_cookies($uh, $ph));
        }
    }

    send_page_header();
    print html_open("CloudVista");
    print_login_form($err, 'register');
    print html_close();
    exit;
}

# ---- SESSION CHECK ----
my $userdir = validate_session($c_uhash, $c_phash);

unless ($userdir) {
    send_page_header();
    print html_open("CloudVista");
    print_login_form('', 'login');
    print html_close();
    exit;
}

my $upload_msg = '';
my $upload_cls = 'alert-ok';


# ---- CHANGE PASSWORD ----
if ($action eq 'changepass') {
    my $old_pass = $q->param('current_password') || '';
    my $new_pass = $q->param('new_password')     || '';
    my $confirm  = $q->param('confirm_password') || '';
    my $err      = '';

    # 1. Check if the current password provided is correct
    if (md5_hex($old_pass) ne $c_phash) {
        $err = 'current password incorrect.';
    } 
    # 2. Basic validation
    elsif ($new_pass eq '' || $confirm eq '') {
        $err = 'all fields required.';
    } elsif (length($new_pass) < 4) {
        $err = 'new password must be at least 4 chars.';
    } elsif ($new_pass ne $confirm) {
        $err = 'new passwords do not match.';
    } else {
        # 3. Perform the move
        my $new_ph  = md5_hex($new_pass);
        my $new_dir = "$STORAGE_ROOT/$c_uhash/$new_ph";

        if (-d $new_dir) {
            $err = 'new password is same as current.';
        } elsif (rename($userdir, $new_dir)) {
            # Success: redirect with new cookies
            send_redirect($SCRIPT_NAME, make_login_cookies($c_uhash, $new_ph));
            exit;
        } else {
            $err = "system error: $!";
        }
    }
    
    $upload_msg = $err;
    $upload_cls = 'alert-err';
}

# # ---- CHANGE PASSWORD ----
# if ($action eq 'changepass') {
#     my $new_pass = $q->param('new_password') || '';
#     my $confirm  = $q->param('confirm_password') || '';
#     my $err      = '';

#     if ($new_pass eq '' || $confirm eq '') {
#         $err = 'all fields required.';
#     } elsif (length($new_pass) < 4) {
#         $err = 'password min 4 chars.';
#     } elsif ($new_pass ne $confirm) {
#         $err = 'passwords do not match.';
#     } else {
#         my $new_ph  = md5_hex($new_pass);
#         my $new_dir = "$STORAGE_ROOT/$c_uhash/$new_ph";

#         if (-d $new_dir) {
#             $err = 'new password cannot be the same as current.';
#         } elsif (rename($userdir, $new_dir)) {
#             # Update session cookies with the new hash so the user stays logged in
#             send_redirect($SCRIPT_NAME, make_login_cookies($c_uhash, $new_ph));
#         } else {
#             $err = 'server error: could not update directory.';
#         }
#     }
#     # If there was an error, re-render the manager with a message
#     $upload_msg = $err;
#     $upload_cls = 'alert-err';
# }

# ---- DELETE ACCOUNT ----
if ($action eq 'deleteaccount') {
    my $confirm_pass = $q->param('confirm_password') || '';
    
    if (md5_hex($confirm_pass) eq $c_phash) {
        # 1. Define the user's root folder (the one containing the password hash folder)
        my $user_root_dir = "$STORAGE_ROOT/$c_uhash";
        
        # 2. Recursive delete helper (since rmdir only works on empty dirs)
        my $delete_sub = sub {
            my ($self, $path) = @_;
            if (-d $path) {
                opendir(my $dh, $path);
                while (my $file = readdir($dh)) {
                    next if $file eq "." || $file eq "..";
                    $self->($self, "$path/$file");
                }
                closedir($dh);
                rmdir($path);
            } else {
                unlink($path);
            }
        };

        # 3. Execute deletion of the entire user hash directory
        $delete_sub->($delete_sub, $user_root_dir);

        # 4. Clear cookies and send to login
        my $c1 = CGI::Cookie->new(-name => 'uhash', -value => '', -expires => '-1d', -path => '/');
        my $c2 = CGI::Cookie->new(-name => 'phash', -value => '', -expires => '-1d', -path => '/');
        print $q->header(-status => '302 Found', -location => $SCRIPT_NAME, -cookie => [$c1, $c2]);
        exit;
    } else {
        $upload_msg = 'incorrect password - account not deleted.';
        $upload_cls = 'alert-err';
    }
}

# ---- DELETE ----
if ($action eq 'delete') {
    my $file = safe_name($q->param('file') || '');
    unlink "$userdir/$file" if -f "$userdir/$file";
    send_redirect($SCRIPT_NAME);
}

# ---- UPLOAD ----
if ($action eq 'upload') {
    my $fh   = $q->upload('file');
    my $name = $q->param('file') || '';
    if (!$fh) {
        $upload_cls = 'alert-err';
        my $cerr = $q->cgi_error || '';
        if ($cerr =~ /too large/i || ($ENV{CONTENT_LENGTH}||0) > $MAX_UPLOAD) {
            $upload_msg = 'file exceeds the 1 GB limit.';
        } else {
            $upload_msg = 'no file selected.';
        }
    } else {
        my $safe  = safe_name($name);
        my $dest  = "$userdir/$safe";
        my $wrote = 0;
        if (!open my $out, '>', $dest) {
            $upload_cls = 'alert-err';
            $upload_msg = 'server error: cannot write file.';
        } else {
            binmode $out;
            my $buf;
            while (my $r = read $fh, $buf, 65536) { print $out $buf; $wrote += $r;
            }
            close $out;
            $upload_msg = "uploaded: $safe (" . fmt_size($wrote) . ")";
        }
    }
}

# ---- FILE MANAGER ----
send_page_header();
print html_open("CloudVista");
print "<div class=\"shell\">\n";

print "<div class=\"topbar\">"
    . "<div class=\"logo\">CloudVista<span></span></div>"
    .
"<div class=\"nav\"><a href=\"${SCRIPT_NAME}?action=logout\">[ logout ]</a></div>"
    . "</div>\n";
if ($upload_msg) {
    print "<div class=\"alert $upload_cls\">" . esc($upload_msg) . "</div>\n";
}

# upload form
print "<div class=\"card\">\n"
    . "<h2>Upload</h2>\n"
    .
"<form method=\"POST\" enctype=\"multipart/form-data\" action=\"$SCRIPT_NAME\">\n"
    . "<input type=\"hidden\" name=\"action\" value=\"upload\">\n"
    .
"<label for=\"uf\">Select file &mdash; max 1 GB</label>\n"
    . "<input type=\"file\" name=\"file\" id=\"uf\">\n"
    .
"<button type=\"submit\" class=\"btn btn-success\">&uarr;&nbsp;Upload</button>\n"
    . "</form>\n"
    . "</div>\n";

# settings / change password & delete account
print "<div class=\"card\">\n"
    . "<details>\n"
    . "<summary style=\"cursor:pointer; font-weight:bold; color:var(--p-clr);\">"
    . "&nbsp;&nbsp;[+] Account Settings"
    . "</summary>\n"
    
    # Password Change Section
    . "<div style=\"margin-top:15px; border-top:1px solid #eee; padding-top:15px;\">\n"
    . "<h3>Change Password</h3>\n"
    . "<form method=\"POST\" action=\"$SCRIPT_NAME\">\n"
    . "<input type=\"hidden\" name=\"action\" value=\"changepass\">\n"
    . "<label for=\"op\">Current Password</label>\n"
    . "<input type=\"password\" name=\"current_password\" id=\"op\" required>\n"
    . "<label for=\"np\">New Password</label>\n"
    . "<input type=\"password\" name=\"new_password\" id=\"np\" required>\n"
    . "<label for=\"cp\">Confirm New Password</label>\n"
    . "<input type=\"password\" name=\"confirm_password\" id=\"cp\" required>\n"
    . "<button type=\"submit\" class=\"btn btn-primary\">&circlearrowright;&nbsp;Update Password</button>\n"
    . "</form>\n"
    . "</div>\n"

    # Delete Account Section
    . "<div style=\"margin-top:25px; border-top:2px dashed #ffcccc; padding-top:15px;\">\n"
    . "<h3 style=\"color:#cc0000;\">Danger Zone</h3>\n"
    . "<p style=\"font-size:0.9em; color:#666;\">Deleting your account will permanently remove all your uploaded files.</p>\n"
    . "<form method=\"POST\" action=\"$SCRIPT_NAME\" onsubmit=\"return confirm('Are you absolutely sure? This cannot be undone.');\">\n"
    . "<input type=\"hidden\" name=\"action\" value=\"deleteaccount\">\n"
    . "<label for=\"dp\">Confirm Password to Delete Account</label>\n"
    . "<input type=\"password\" name=\"confirm_password\" id=\"dp\" required>\n"
    . "<button type=\"submit\" class=\"btn\" style=\"background:#cc0000; color:white; border:none; padding:8px 15px; border-radius:4px; cursor:pointer;\">"
    . "&times;&nbsp;Permanently Delete My Account</button>\n"
    . "</form>\n"
    . "</div>\n"

    . "</details>\n"
    . "</div>\n";
# # settings / change password form in a toggle drawer
# print "<div class=\"card\">\n"
#     . "<details>\n" # The "Drawer" container
#     . "<summary style=\"cursor:pointer; font-weight:bold; color:var(--p-clr);\">"
#     . "&nbsp;&nbsp;[+] Account Settings / Change Password"
#     . "</summary>\n"
#     . "<div style=\"margin-top:15px; border-top:1px solid #eee; padding-top:15px;\">\n"
#     . "<form method=\"POST\" action=\"$SCRIPT_NAME\">\n"
#     . "<input type=\"hidden\" name=\"action\" value=\"changepass\">\n"
    
#     . "<label for=\"op\">Current Password</label>\n"
#     . "<input type=\"password\" name=\"current_password\" id=\"op\" required>\n"
    
#     . "<label for=\"np\">New Password</label>\n"
#     . "<input type=\"password\" name=\"new_password\" id=\"np\" required>\n"
    
#     . "<label for=\"cp\">Confirm New Password</label>\n"
#     . "<input type=\"password\" name=\"confirm_password\" id=\"cp\" required>\n"
    
#     . "<button type=\"submit\" class=\"btn btn-primary\">&circlearrowright;&nbsp;Update Password</button>\n"
#     . "</form>\n"
#     . "</div>\n"
#     . "</details>\n"
#     . "</div>\n";

# # settings form
# print "<div class=\"card\">\n"
#     . "<h2>Settings</h2>\n"
#     . "<form method=\"POST\" action=\"$SCRIPT_NAME\">\n"
#     . "<input type=\"hidden\" name=\"action\" value=\"changepass\">\n"
#     . "<label for=\"np\">New Password</label>\n"
#     . "<input type=\"password\" name=\"new_password\" id=\"np\">\n"
#     . "<label for=\"cp\">Confirm New Password</label>\n"
#     . "<input type=\"password\" name=\"confirm_password\" id=\"cp\">\n"
#     . "<button type=\"submit\" class=\"btn btn-primary\">&circlearrowright;&nbsp;Update Password</button>\n"
#     . "</form>\n"
#     . "</div>\n";

# file list
my @files;
if (opendir my $dh, $userdir) {
    while (my $f = readdir $dh) {
        next if $f eq '.'
|| $f eq '..';
        next unless -f "$userdir/$f";
        my @st = stat "$userdir/$f";
        push @files, { name => $f, size => $st[7]||0, mtime => $st[9]||0 };
    }
    closedir $dh;
}
@files = sort { $b->{mtime} <=> $a->{mtime} } @files;

print "<div class=\"card\">\n<h2>Files</h2>\n";
if (@files) {
    print "<table>\n"
        .
"<thead><tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr></thead>\n"
        . "<tbody>\n";
for my $f (@files) {
        my $enc   = $q->escape($f->{name});
        my $dname = esc($f->{name});
        my $sz    = fmt_size($f->{size});
        my $dt    = strftime("%Y-%m-%d %H:%M", localtime($f->{mtime}));
        print "<tr>"
            .
"<td class=\"fname\">$dname</td>"
            .
"<td class=\"fsize\">$sz</td>"
            .
"<td class=\"fdate\">$dt</td>"
            .
"<td class=\"factions\">"
            .
"<a class=\"dl\" href=\"${SCRIPT_NAME}?action=download&amp;file=${enc}\">"
            .
"&darr;&nbsp;download</a>"
            .
" <a class=\"del\" href=\"${SCRIPT_NAME}?action=delete&amp;file=${enc}\""
            .
" onclick=\"return confirm('Delete ${dname}?')\">"
            .
"&#x2715;&nbsp;delete</a>"
            . "</td></tr>\n";
    }

    print "</tbody>\n</table>\n";
    my $used = dir_size($userdir);
    my $pct  = $MAX_UPLOAD > 0 ? int($used * 100 / $MAX_UPLOAD) : 0;
    $pct     = 100 if $pct > 100;
    my $cnt  = scalar @files;
    print "<div class=\"bar-bg\"><div class=\"bar-fg\" style=\"width:${pct}%\"></div></div>\n"
        . "<div class=\"usage\">" . fmt_size($used) .
" used &mdash; $cnt file(s)</div>\n";

} else {
    print "<div class=\"empty\">no files yet &mdash; upload something above</div>\n";
}

print "</div>\n";   # files card
print "</div>\n";   # shell
print html_close();
exit;
##############################################################
# LOGIN / REGISTER FORM  (called after headers already sent)
##############################################################
sub print_login_form {
    my ($msg, $tab) = @_;
    $tab ||= 'login';

    my $ltab = $tab eq 'login'    ? 'tab active' : 'tab';
    my $rtab = $tab eq 'register' ? 'tab active' : 'tab';

    print "<div class=\"shell\"><div class=\"login-wrap\"><div class=\"login-box\">\n";
    print "<div class=\"logo-big\">CloudVista</div>\n";
    if ($msg) {
        print "<div class=\"alert alert-err\">" . esc($msg) . "</div>\n";
    }

    print "<div class=\"card\">\n"
        .
"<div class=\"tabs\">"
        .
"<a class=\"$ltab\" href=\"$SCRIPT_NAME\">login</a>"
        .
"<a class=\"$rtab\" href=\"${SCRIPT_NAME}?action=register\">register</a>"
        . "</div>\n";
    if ($tab eq 'login') {
        print "<form method=\"POST\" action=\"$SCRIPT_NAME\">\n"
            .
"<input type=\"hidden\" name=\"action\" value=\"login\">\n"
            .
"<label for=\"lu\">Username</label>\n"
            .
"<input type=\"text\" name=\"username\" id=\"lu\" autocomplete=\"username\" autofocus>\n"
            .
"<label for=\"lp\">Password</label>\n"
            .
"<input type=\"password\" name=\"password\" id=\"lp\" autocomplete=\"current-password\">\n"
            .
"<button type=\"submit\" class=\"btn btn-primary\" style=\"width:100%\">login &rarr;</button>\n"
            . "</form>\n";
    } else {
        print "<form method=\"POST\" action=\"$SCRIPT_NAME\">\n"
            .
"<input type=\"hidden\" name=\"action\" value=\"register\">\n"
            .
"<label for=\"ru\">Username</label>\n"
            .
"<input type=\"text\" name=\"username\" id=\"ru\" autocomplete=\"username\" autofocus>\n"
            .
"<label for=\"rp\">Password</label>\n"
            .
"<input type=\"password\" name=\"password\" id=\"rp\" autocomplete=\"new-password\">\n"
            .
"<label for=\"rc\">Confirm Password</label>\n"
            .
"<input type=\"password\" name=\"confirm\" id=\"rc\" autocomplete=\"new-password\">\n"
            .
"<button type=\"submit\" class=\"btn btn-success\" style=\"width:100%\">"
            .
"create account &rarr;</button>\n"
            . "</form>\n";
    }

    print "</div>\n</div>\n</div>\n</div>\n";
}
