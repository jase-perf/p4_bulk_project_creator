# p4_bulk_project_creator

**NOTE: This is a modified version of the original p4_bulk_project_creator.**

This branch is just for creating users and groups and has slightly different features for things like
setting up default passwords for users and specifying custom usernames.

This python gui application allows you to create multiple users and groups from a csv file.

This is an example of the csv file format:
```csv
Name,Username,E-mail,Group,Password
Alice Smith,AliceSmith,asmith@student.email,Modeling,fdsoeih2#$!
Bob Johnson,BobJohnson,bjohnson@student.email,Modeling,dfgjkl34@#$
Charlie Brown,CharlieBrown,cbrown@student.email,Simulation,tyuiop98@#$
David Lee,DavidLee,dlee@student.email,Visualization,qwerty12@#$
```

(Examples of good and bad CSV files for testing can be found in the `data/` folder.)

**Name**: The name field is used for the user's full name.

**Username**: The username field is used for the user's username in Helix Core.

**E-mail**: Usernames in Helix Core will be the first part of the email address (before the @ symbol).

The email field must match the email domain specified in the config file. If no email domain is specified, any email address will be accepted. (see below)

**Group_Name**: The group name field is used to specify which group the user will be added to.

Be sure you add lines to your p4 protect table for these groups so that users can login to the server.

**Password**: The password field is used for the user's initial password. If no password is specified, the default password will be used. (see below)

## Requirements
- P4 CLI
- A Helix Core server to connect to
- Super user login to P4 server

## Installation
### Precompiled Binary
The `bin` directory contains precompiled binaries for Windows and MacOS arm64 (aka M-series processors)

1. Clone this repo to a location on your computer:
    ```
    git clone git@github.com:vertigojc/p4_bulk_project_creator.git
    ```
2. Login to P4Admin as a super user and go to **Tools > Manage Tools > Custom Tools...**
    ![Tools > Manage Tools > Custom Tools...](images/Tools-Manage_Tools-Custom_Tools.png)
3. On the Custom Tools windows, select **New > Tool...**
    ![Add New Tool](images/New%20Tool.png)
4. On the Add Local Tool Window, fill in these fields:
    
    1. **Name:** Enter whatever name you would like to show up in the tools menu.
    2. **Application:** Browse to the path to the executable file for your operating system (.exe for windows, (arm64) for M-series OSX)
    3. **Start In:** The `Start In` directory is where the program will look for the `config.ini` file, and where it will output logs as `log.txt` and undo files (for easy undoing if you need to reset) as `undo_commands-[YYYY-MM-DD-HH-MM-SS].txt`.
    4. **Refresh Helix Admin:** This checkbox will make sure you see the results of your changes right away after closing the tool.
    
    ![Add Local Tool](images/Add%20Local%20Tool.png)
5. Click **OK** on all the windows. Now, when you go to the Tools menu at the top, you should see your new custom tool!
    ![New Custom Tool in Menu](images/Tool%20In%20Menu.png)

### Python Install
If you would prefer not to use the precompiled binaries or you wish to customize the code, there are a couple additional steps.

1. You will need to have Python 3.8 or higher (tested with 3.11) installed.
2. After cloning the repository, cd to the repo directory and install requirements (PyQt6 and P4Python)
    ```
    pip install -r requirements.txt
    ```
3. Verify that it runs.
    ```
    python app/main.py
    ```
4. Follow the steps above for adding a custom tool to P4Admin but **Application** and **Arguments** will be different.

    1. **Application:** Here, enter the path to your python installation.
    2. **Arguments:** For arguments, enter the path to the `app/main.py` script inside the repository.
    3. **Start In:** See above for explanation, but this is where the config and logs will be.


## Configuration
The `config.ini` file can be edited to add a custom email domain and custom initial password for created users.

By default, any standard email address will be accepted.

By default, the initial password for all users will be `ChangeMe123!`.

By default, users will NOT be required to reset their password on first login. To enable this feature, set `REQUIRE_PASSWORD_RESET = true`.

For example, if you wanted to only validate email addresses that end in @myuniversity.edu, change the default password to "myUniversitySecret#45", and require a password reset on first login, set the `config.ini` file to:

```
[DEFAULT]
EMAIL_DOMAIN = myuniversity.edu
DEFAULT_PASSWORD = myUniversitySecret#45
REQUIRE_PASSWORD_RESET = true
```

## Notes
- Server must be 2022.1 or higher for the undo commands to work properly when removing streams.
