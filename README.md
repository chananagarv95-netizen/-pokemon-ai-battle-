First, clone this repository. This will download both the server to run it locally as well as the client and implementation files.

```
git clone https://github.com/Aries-IITD/Tryst-RL-Codebase.git server
```

You also need to have Node.js installed v- SPECIFICALLY INSTALL v21.1.0. Remember to add it to PATH.
Also, Python3 (preferably the latest version) is required.

```
./pokemon-showdown 7850 --no-security
```
(Linux)

or 

```
node pokemon-showdown 7850 --no-security
```
(Windows)

You can also choose the change the 7850 to another port number if you need to, but you will need to change client/env.txt if you do.
Your server is now hosted locally and running. To stop it hit Ctrl-C in the terminal and just type the command in again to run it again.

Enter `localhost:7850` in your browser to view the battles/actually participate in one! (or localhost:<port_no> if you changed it)
Add yourself as an administrator to your local server by editing `server/config/usergroups.csv`.
Simply add a line that is your username (you can create an account by visiting the site in your browser) followed by a , and ~.
For example my username is `TheAbry`, so my `usergroups.csv` looks like:
```
TheAbry,~
```
Then when you log in as this username you will be able to see all battles taking place on your server.

For the bot client, in the `client` folder create a venv and install all dependencies from `requirements.txt`.
```
pip install -r requirements.txt
```
Even if the pip install raises an error, you can try running the next steps and installing required modules independently if it raises an error.

Put the port number for your server in the link in `client/env.txt`. Change the second line to your assigned code.

In order to send challenges to the bots or queue up on the official competition ladder, you will have to connect to the competition server. For this, change the first line to the IP of the server instead. The IP (and port) for the server is given in the env.txt as well.

You can run 
```
python(or python3) driver.py -h
```
to check all the command line arguments. You can change the mode to 
- Battle against one of your own AIs, using the battle argument
- Wait on the hosted ladder for battles, using the ladder argument. While your ELO gained won't be counted, it is encouraged that everyone does this so you can get a wider experience by battling others' bots.
- Send challenges to other users, using the challenge argument (used to send challenges to the bots).

We have given 5 options for AIs: random, ai1, ai2, ai3, ai4. Random is pre-implemented, while ai1-ai4 can be implemented in `ai.py`.

If you get an error for no module `poke_env`, try pip installing it separately using `pip install poke_env` or upgrading your pip then repeating the pip install steps again.
If you get an error in running the driver.py after a crash, restart the server.

The Bot IDs to send challenges to, to test your implementations, are:
5ccf9bAIPly11
2d8493AIPly11
b815fcAIPly11
e75c45AIPly11

As an example, you can do
```
python driver.py challenge ai1 5ccf9bAIPly11 --replay
```
to make your ai1 fight the given bot, and download the replay to your device.

Poke-Env library is open source and available at https://github.com/hsahovic/poke-env/




