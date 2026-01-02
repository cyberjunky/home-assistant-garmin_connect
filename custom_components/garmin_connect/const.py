"""Constants for the Garmin Connect integration."""

from datetime import timedelta

DOMAIN = "garmin_connect"
DATA_COORDINATOR = "coordinator"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)
CONF_MFA = "mfa_code"

DAY_TO_NUMBER = {
    "Mo": 1,
    "M": 1,
    "Tu": 2,
    "We": 3,
    "W": 3,
    "Th": 4,
    "Fr": 5,
    "F": 5,
    "Sa": 6,
    "Su": 7,
}

LEVEL_POINTS = {
    1: 0,
    2: 20,
    3: 60,
    4: 140,
    5: 300,
    6: 620,
    7: 1260,
    8: 2540,
    9: 5100,
    10: 10220,
}

GEAR_ICONS = {
    "Shoes": "mdi:shoe-sneaker",
    "Bike": "mdi:bike",
    "Other": "mdi:basketball",
    "Golf Clubs": "mdi:golf",
}


class ServiceSetting:
    """Options for the service settings."""

    ONLY_THIS_AS_DEFAULT = "set this as default, unset others"
    DEFAULT = "set as default"
    UNSET_DEFAULT = "unset default"


class Gear:
    """Gear attribute keys."""

    UUID = "uuid"
    TYPE_KEY = "typeKey"
    TYPE_ID = "typeId"
    USERPROFILE_ID = "userProfileId"
    ACTIVITY_TYPE_PK = "activityTypePk"

