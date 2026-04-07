# CloudVista

CloudVista is a simple cloud file storage site that allows users to register, login, upload, download, and delete files. 

## Features
- Files are **not encrypted** - they are stored as-is in the storage directory
- User directories are created using MD5 hashes of usernames
- Password hashes are created using MD5
- Files are stored in a designated STORAGE_ROOT directory (default: `/var/www/storage`)
- 1GB file size limit per upload
- Cookie-based session management (30-day expiration)
- Users can change their password
- Users can delete their account (which removes all files)

## Setup & Configuration

Configuration is done by editing the variables in the `cloudvista.cgi` script:

```perl
my $STORAGE_ROOT = "/var/www/storage"; # must be writable by httpd user
my $MAX_UPLOAD   = 1073741824;         # 1 GB
my $SCRIPT_NAME  = $ENV{SCRIPT_NAME} || "/cgi-bin/cloudvista.cgi";
my $COOKIE_DAYS  = 30;
```

## Requirements

- Perl 5.8+ with core modules
- A web server with CGI support (Apache, Nginx with CGI wrapper, etc.)
- The storage directory must be writable by the web server user

## Installation

1. Place `cloudvista.cgi` in your web server's CGI directory
2. Make it executable: `chmod 755 cloudvista.cgi`
3. Create and configure the storage directory:
   ```bash
   mkdir -p /var/www/storage
   chown www-data:www-data /var/www/storage  # adjust user for your web server
   chmod 750 /var/www/storage
   ```
4. Update `$STORAGE_ROOT` in the script if needed
5. Access via your web server's CGI endpoint

## Usage

Users can:
- Register a new account with username and password
- Login to access their file storage
- Upload files (up to 1GB each)
- Download their files
- Delete individual files
- Change their password
- Delete their account and all files