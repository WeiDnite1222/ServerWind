# ServerWind


## Installation
##### Python 3.12 (or newer), git, and uv is required

### Clone repository
```
# Main repo
git clone https://repo.weispace.net/wei/ServerWind.git

# Mirror repo
git clone https://github.com/WeiDnite1222/ServerWind.git
```

### Configure virtual environment and install dependencies

```
uv python pin 3.12.10
uv pip install -r requirements.txt
```

## Usage

### Create .env file

```
DISCORD_TOKEN="YOUR-TOKEN-HERE"
```
Replace `YOUR-TOKEN-HERE` to your Discord bot token.

### Use CF DDNSUpdater

#### Go to Cloudflare Dashboard > Click profile icon > Profile > Create Token > Edit zone token to generate token

Open 'config/cf.yaml' and replace some values.

```
allowedBroadcastServer: []
cfSecret: YOUR-CF-SECRET-KEY # Replace to your cf secret token
doIPCheckInterval: 600 # Next IP check interval (sec)
doUpdate: true # set it to true to enable updater
domains: [] # subdomains that you want auto-update (Example: { "name": "www.example.com", "proxied": true })
zone: null # zone of your domain name (such as example.com)
ddnsBroadcastCode: code-here # IMPORTANT: Replace it that only you know
```

Remember to restart the tool after you save the config file.