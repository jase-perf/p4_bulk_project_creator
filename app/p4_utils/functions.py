import logging

from p4_utils import p4

import logging

# Create a custom logger
logger = logging.getLogger("main.functions")


def check_remaining_seats():
    license_info = p4.run("license", "-u")
    return int(license_info[0]["userLimit"]) - int(license_info[0]["userCount"])


def check_users(new_user_list):
    """Check if the users in user_list exist in the Perforce server."""
    current_user_names = [user["User"] for user in p4.run("users")]
    users_to_add = [
        user for user in new_user_list if user["User"] not in current_user_names
    ]
    logger.debug(f"Users to add: {len(users_to_add)}")
    return users_to_add


def create_user(user_to_add: dict):
    p4.input = user_to_add
    return p4.run("user", "-f", "-i")


def set_initial_password(user: str, password: str):
    p4.input = password
    p4.run("passwd", user)
    return p4.run("admin", "resetpassword", "-u", user)


def get_existing_groups():
    """Check if the groups in group_list exist in the Perforce server."""
    current_groups = p4.run("groups")
    current_group_names = {group["group"] for group in current_groups}
    return [p4.run_group("-o", group_name)[0] for group_name in current_group_names]


def create_group(group_to_add: dict):
    p4.input = group_to_add
    return p4.run("group", "-i")


def check_depots(new_group_list):
    # Groups and Depots have the same name
    """Check if the depots in depot_list exist in the Perforce server."""
    current_depots = p4.run("depots")
    current_depot_names = [depot["name"] for depot in current_depots]
    logger.debug(f"Current depots: {current_depot_names}")
    logger.debug(f"New depot names: {new_group_list}")
    depots_to_add = [
        depot for depot in new_group_list if depot not in current_depot_names
    ]
    logger.debug(f"Depots to add: {len(depots_to_add)}")
    return depots_to_add


def create_depot(depot_name, depot_type):
    # TODO: Add support for different stream depths
    new_depot = p4.fetch_depot("-t", f"{depot_type}", f"{depot_name}")
    p4.input = new_depot
    return p4.run("depot", "-i")


def get_streams(template_depot_name, new_depot_name):
    exclude_keys = [
        "Update",
        "Access",
        "baseParent",
        "streamSpecDigest",
        "firmerThanParent",
    ]
    streams = p4.run_streams(
        "-F", f"Stream=//{template_depot_name}/... | Parent=//{template_depot_name}/..."
    )
    streams_details = [p4.run_stream("-o", stream["Stream"])[0] for stream in streams]
    for stream in streams_details:
        for key in exclude_keys:
            stream.pop(key, None)
        for key in stream:
            if isinstance(stream[key], str):
                stream[key] = stream[key].replace(template_depot_name, new_depot_name)
            elif isinstance(stream[key], list):
                stream[key] = [
                    value.replace(template_depot_name, new_depot_name)
                    for value in stream[key]
                ]

    # Function to get the parents in order
    def get_parents(stream):
        parents = []
        while stream:
            parents.insert(0, stream["Stream"])
            stream = next(
                (
                    item
                    for item in streams_details
                    if item["Stream"] == stream["Parent"]
                ),
                None,
            )
        return parents

    # Sorting the list
    sorted_list = sorted(streams_details, key=lambda x: get_parents(x))

    return sorted_list


def create_stream(stream_to_add: dict):
    p4.input = stream_to_add
    return p4.run("stream", "-i")


def create_branch_maps(template_depot_name, new_depot_name):
    streams = p4.run_streams(
        "-F", f"Stream=//{template_depot_name}/... | Parent=//{template_depot_name}/..."
    )
    branch_maps = []
    for stream in streams:
        branch_map = p4.fetch_branch(f"populate_{new_depot_name}_{stream['Stream']}")
        branch_map["View"] = [
            f"{stream['Stream']}/... {stream['Stream'].replace(template_depot_name, new_depot_name)}/..."
        ]
        logger.debug(branch_map)
        p4.save_branch(branch_map)
        branch_maps.append(branch_map["Branch"])
    return branch_maps


def populate_new_depot(template_depot_name, new_depot_name):
    logger.debug(f"Populating with initial template for {new_depot_name}...")
    branch_maps = create_branch_maps(template_depot_name, new_depot_name)
    for branch_map in branch_maps:
        p4.run_populate(
            "-d",
            f"Populating with initial template for {new_depot_name}",
            "-b",
            branch_map,
        )
        p4.run_branch("-d", branch_map)


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
    logger.debug(f"Permissions to add: {len(permissions_to_add)}")
    return permissions_to_add


def create_permissions(permissions_to_add):
    protect_table = p4.run("protect", "-o")[0]
    protect_table["Protections"] = permissions_to_add + protect_table["Protections"]
    p4.input = protect_table
    return p4.run("protect", "-i")


def get_template_depots(template_pattern="template"):
    return p4.run("depots", "-E", f"*{template_pattern}*")
