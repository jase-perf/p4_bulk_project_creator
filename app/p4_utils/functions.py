from p4_utils import p4


def check_remaining_seats():
    license_info = p4.run("license", "-u")
    return int(license_info[0]["userLimit"]) - int(license_info[0]["userCount"])


def check_users(new_user_list):
    """Check if the users in user_list exist in the Perforce server."""
    current_users = p4.run("users")
    current_user_names = [user["User"] for user in current_users]
    users_to_add = [user for user in new_user_list if user not in current_user_names]
    print(f"Users to add: {len(users_to_add)}")
    return users_to_add


def check_groups(new_group_list):
    """Check if the groups in group_list exist in the Perforce server."""
    current_groups = p4.run("groups")
    current_group_names = [group["group"] for group in current_groups]
    groups_to_add = [
        group for group in new_group_list if group not in current_group_names
    ]
    print(f"Groups to add: {len(groups_to_add)}")
    return groups_to_add


def check_depots(new_group_list):
    # Groups and Depots have the same name
    """Check if the depots in depot_list exist in the Perforce server."""
    current_depots = p4.run("depots")
    current_depot_names = [depot["name"] for depot in current_depots]
    depots_to_add = [
        depot for depot in new_group_list if depot not in current_depot_names
    ]
    print(f"Depots to add: {len(depots_to_add)}")
    return depots_to_add


def check_permissions(new_group_list):
    """Check if the permissions in permission_list exist in the Perforce server."""
    current_permissions = p4.run("protect", "-o")[0]["Protections"]
    new_permissions = [
        f"write group {group_name} * //{group_name}/..."
        for group_name in new_group_list
    ]
    permissions_to_add = [
        permission
        for permission in new_permissions
        if permission not in current_permissions
    ]
    print(f"Permissions to add: {len(permissions_to_add)}")
    return permissions_to_add


def get_template_depots(template_pattern="template"):
    return p4.run("depots", "-E", f"*{template_pattern}*")
