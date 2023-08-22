# p4_bulk_project_creator

This python gui application allows you to create multiple users, groups and depots from a csv file.
Additionally, it will populate the depots with streams and populate the streams with files based on a template depot. In order for a depot to show up on the template list, the depot must contain the word "template" in it's name.

This is an example of the csv file format:
```csv
Name,E-mail,Group_Name,Owner
First Last,person1@student.email,ClassA_Group01,True
Student Middle Lastname,person2@student.email,ClassA_Group01,
Justonename,person3@student.email,ClassA_Group02,
```

#### Name
The name field is used for the user's full name.

#### E-mail
Usernames in Helix Core will be the first part of the email address (before the @ symbol).

The email field must match the email domain specified in the config file. If no email domain is specified, any email address will be accepted. (see below)

#### Group_Name
The group name field is used to specify which group the user will be added to.

The group names are also the names of the depots which will be created.

The permissions will be updated so that users in each group can write to the depot of the same name.

#### Group Owner
If this field is set to true, the user will be set as an owner of the group, which will allow them to add and remove users from the group.
This can be set to false or left blank for other users.

## Requirements
- Python 3.8+
- P4 CLI
- A Helix Core server to connect to
- Super user login to P4 server
## Installation
Clone the repo and run `pip install -r requirements.txt`
This will install the p4python api and PyQt6.

## Configuration
The `config.ini` file can be edited to add a custom email domain.
By default, any standard email address will be accepted.

For example, if you wanted to only validate email addresses that end in @myuniversity.edu, set the `config.ini` file to:

```
[DEFAULT]
EMAIL_DOMAIN = myuniversity.edu
```

## Notes
- Server must be 2022.1 or higher for the undo commands to work properly when removing streams.
