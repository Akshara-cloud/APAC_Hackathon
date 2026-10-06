# AWS EC2 Setup and Bot Launch Guide (Roostoo APAC Hackathon)

This guide walks you step-by-step through setting up an AWS EC2 instance and deploying your Roostoo trading bot to run continuously in the cloud.

---

## Step 1: AWS EC2 Instance Creation & Sign-In

1. **Log in to AWS Console** using the credentials provided by the hackathon organizers.
2. Go to **EC2 Dashboard** and click **Launch Instance**.
3. **Configure Instance:**
   - **Name:** `Roostoo-Trading-Bot`
   - **OS Image:** Ubuntu 22.04 LTS (64-bit x86) or Amazon Linux 2023.
   - **Instance Type:** `t2.micro` or `t3.micro` (Free tier eligible).
   - **Key Pair:** Create or select an existing SSH Key Pair (download the `.pem` file, e.g., `roostoo-key.pem`).
   - **Network & Security Groups:**
     - Allow SSH traffic (Port 22) from your IP.
4. Click **Launch Instance** and copy your instance's **Public IPv4 Address** (e.g. `54.123.45.67`).

---

## Step 2: SSH into your AWS EC2 Instance

Open your local terminal and run:

```bash
# Set key permissions
chmod 400 roostoo-key.pem

# SSH into EC2 (Replace with your EC2 Public IP)
ssh -i roostoo-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

---

## Step 3: Server Setup & Repository Cloning

Once inside your EC2 server, execute the following commands:

```bash
# 1. Update system packages and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git tmux

# 2. Clone the Hackathon Repository
git clone https://github.com/Akshara-cloud/APAC_Hackathon.git
cd APAC_Hackathon/APAC_Hackathon

# 3. Create and activate a Virtual Environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Python requirements
pip install -r requirements.txt
```

---

## Step 4: Configure Credentials (.env)

Create and populate the `.env` file with your Roostoo credentials:

```bash
nano .env
```

Paste your team credentials into `.env`:

```env
ROOSTOO_API_KEY=your_actual_api_key
ROOSTOO_SECRET_KEY=your_actual_secret_key
ROOSTOO_BASE_URL=https://mock-api.roostoo.com

# Bot parameters
DRY_RUN=False
POSITION_SIZE=0.10
POLL_INTERVAL=10
FAST_WINDOW=3
SLOW_WINDOW=6
```

*(Press `Ctrl + O` then `Enter` to save, and `Ctrl + X` to exit nano)*

---

## Step 5: Test & Launch the Bot in Background

### Option A: Using `tmux` (Recommended)

`tmux` allows the bot to run continuously even after closing your SSH terminal.

```bash
# Start a new tmux session
tmux new -s roostoo_bot

# Inside tmux, activate venv and run the bot
source venv/bin/activate
python3 roostoo_api/bot.py
```

* To detach from tmux: Press `Ctrl + B` then press `D`.
* To re-attach to view logs anytime later: `tmux attach -t roostoo_bot`

### Option B: Using `nohup`

```bash
nohup python3 roostoo_api/bot.py > bot.log 2>&1 &

# Monitor live logs
tail -f bot.log
```

---

## Step 6: Verification

To verify that your bot is active and communicating with Roostoo:

1. Check running processes: `ps aux | grep python3`
2. Check log output: `tail -n 20 bot.log` or inside `tmux attach -t roostoo_bot`.
