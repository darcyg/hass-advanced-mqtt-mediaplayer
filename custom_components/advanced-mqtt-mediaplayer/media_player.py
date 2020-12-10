import logging
import homeassistant.loader as loader
import hashlib
import voluptuous as vol
import base64
import requests
import math
import homeassistant.helpers.config_validation as cv

from urllib.parse import urlparse
from typing import Optional
from homeassistant.util import dt
from homeassistant.exceptions import TemplateError, NoEntitySpecifiedError
from homeassistant.helpers.script import Script
from homeassistant.helpers.event import TrackTemplate, async_track_template_result, async_track_state_change
from homeassistant.components import mqtt
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_STOP,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SEEK,

    MEDIA_TYPE_MUSIC,
)

from homeassistant.const import (
    CONF_NAME,
    STATE_ON,
    STATE_OFF,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)

DEPENDENCIES = ["mqtt"]

_LOGGER = logging.getLogger(__name__)

STATE_NEXT = "next"
STATE_PREV = "prev"
STATE_STOP = "stop"

# ACTIONS
ACTIONS = "actions"

TITLE_TOPIC = "title"
ARTIST_TOPIC = "artist"
ALBUM_TOPIC = "album"
SERIES_TITLE_TOPIC = "series_title"
SEASON_TOPIC = "season"
EPISODE_TOPIC = "episode"
APP_TOPIC = "app"
VOLUME_TOPIC = "volume"
VOLUME_UP_TOPIC = "volume_up"
VOLUME_DOWN_TOPIC = "volume_down"
COVER_TOPIC = "cover"
STATE_TOPIC = "state"
MUTE_TOPIC = "mute"
NEXT_TOPIC = "next"
PREV_TOPIC = "prev"
STOP_TOPIC = "stop"
TYPE_TOPIC = "type"
SOURCE_TOPIC = "source"
ICON_TOPIC = "icon"
DURATION_TOPIC = "duration"
POSITION_TOPIC = "position"
SEEK_TOPIC = "seek"
FEATURES_TOPIC = "features"

STAT_TOPIC = "stat"
SET_TOPIC = "set"
DEFAULT = "default"
SOURCE_LIST = "source_list"
DISABLED_IN_STATE = "disabled_in_state"

BASE_FEATURES = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(ACTIONS):
            vol.All({
                vol.Required(STATE_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DEFAULT, default=STATE_OFF): cv.string,
                    }),
                vol.Required(TITLE_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(ARTIST_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(ALBUM_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(APP_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(SERIES_TITLE_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(SEASON_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(EPISODE_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(COVER_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(VOLUME_TOPIC):
                    vol.All({
                        vol.Optional(STAT_TOPIC): cv.string,
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DEFAULT, default=0): cv.positive_int,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(VOLUME_UP_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(VOLUME_DOWN_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(MUTE_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(NEXT_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(PREV_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(STOP_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(TYPE_TOPIC):
                    vol.All({
                        vol.Optional(STAT_TOPIC): cv.string,
                        vol.Optional(DEFAULT, default=MEDIA_TYPE_MUSIC): cv.string,
                    }),
                vol.Optional(SOURCE_TOPIC):
                    vol.All({
                        vol.Optional(STAT_TOPIC): cv.string,
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DEFAULT, default=None): cv.string,
                        vol.Optional(SOURCE_LIST, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(ICON_TOPIC):
                    vol.All({
                        vol.Optional(STAT_TOPIC): cv.string,
                        vol.Optional(DEFAULT, default="mdi:cast"): cv.string,
                    }),
                vol.Optional(DURATION_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(POSITION_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
                vol.Optional(SEEK_TOPIC):
                    vol.All({
                        vol.Required(SET_TOPIC): cv.string,
                        vol.Optional(DISABLED_IN_STATE, default=[]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }),
                vol.Optional(FEATURES_TOPIC):
                    vol.All({
                        vol.Required(STAT_TOPIC): cv.string,
                    }),
            }),
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    entity_name = config.get(CONF_NAME)

    actions = config.get(ACTIONS)

    device = AdvancedMQTTMediaPlayer(entity_name, actions, hass)

    add_entities([device])

class AdvancedMQTTMediaPlayer(MediaPlayerEntity):

    def __init__(self, name, actions, hass):
        self.hass = hass
        self._domain = __name__.split(".")[-2]
        self._name = name

        self._features = BASE_FEATURES

        self._volume = None
        self._title = None
        self._artist = None
        self._album = None
        self._app = None
        self._series_title = None
        self._season = None
        self._episode = None
        self._state = None
        self._duration = None
        self._position = None
        self._position_updated_at = None
        self._cover = None
        self._source = None
        self._source_list = []
        self._is_mute = False
        self._type = MEDIA_TYPE_MUSIC
        self._icon = None

        self._prev_volume = None
        self._publish_topics = {}
        self._disabled_in_state = {}

        self._unique_id = "{}-{}".format(self._domain, name)

        _updated = []

        for actionName, actions in actions.items():
           for action, value in actions.items():
               if action == STAT_TOPIC:
                   if getattr(self, actionName + '_listener') is not None:
                       mqtt.subscribe(self.hass, value, getattr(self, actionName + '_listener'))
               if action == SET_TOPIC:
                   self._publish_topics[actionName] = value
               if action == DEFAULT:
                   self.__dict__["_" + actionName] = value
               if action == SOURCE_LIST:
                   self._source_list = value
               if action == DISABLED_IN_STATE:
                   self._disabled_in_state[actionName] = value

               if actionName not in _updated:
                   self.update_features(actionName)
                   _updated.append(actionName)

        if self._publish_topics[STATE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STATE_TOPIC], self._state)

    async def features_listener(self, msg):
        self._features = int(msg.payload)
        self.schedule_update_ha_state(True)

    async def title_listener(self, msg):
        if str(msg.payload) == 'none':
           self._title = None

           self.schedule_update_ha_state(True)
           return

        self._title = str(msg.payload)
        self.schedule_update_ha_state(True)

    async def artist_listener(self, msg):
        if str(msg.payload) == 'none':
           self._artist = None

           self.schedule_update_ha_state(True)
           return

        self._artist = str(msg.payload)
        self.schedule_update_ha_state(True)

    async def album_listener(self, msg):
        if str(msg.payload) == 'none':
           self._album = None

           self.schedule_update_ha_state(True)
           return

        self._album = str(msg.payload)
        self.schedule_update_ha_state(True)

    async def app_listener(self, msg):
        if str(msg.payload) == 'none':
           self._app = None

           self.schedule_update_ha_state(True)
           return

        self._app = str(msg.payload)
        self.schedule_update_ha_state(True)

    async def series_title_listener(self, msg):
        if str(msg.payload) == 'none':
           self._series_title = None

           self.schedule_update_ha_state(True)
           return

        self._series_title = str(msg.payload)
        self.schedule_update_ha_state(True)

    async def season_listener(self, msg):
        if str(msg.payload) == 'none':
           self._season = None

           self.schedule_update_ha_state(True)
           return

        self._season = int(msg.payload)
        self.schedule_update_ha_state(True)

    async def episode_listener(self, msg):
        if str(msg.payload) == 'none':
           self._episode = None

           self.schedule_update_ha_state(True)
           return

        self._episode = int(msg.payload)
        self.schedule_update_ha_state(True)

    async def state_listener(self, msg):
        self._state = msg.payload
        self.schedule_update_ha_state(True)

    async def duration_listener(self, msg):
        if str(msg.payload) == 'none':
           self._duration = None

           self.schedule_update_ha_state(True)
           return

        self._duration = float(msg.payload)
        self.schedule_update_ha_state(True)

    async def position_listener(self, msg):
        self._position_updated_at = dt.utcnow()

        if str(msg.payload) == 'none':
           self._position = None

           self.schedule_update_ha_state(True)
           return

        self._position = float(msg.payload)
        self.schedule_update_ha_state(True)

    async def volume_listener(self, msg):
        self._volume = int(msg.payload)
        self.schedule_update_ha_state(True)

    async def type_listener(self, msg):
        self._type = msg.payload
        self.schedule_update_ha_state(True)

    async def source_listener(self, msg):
        self._source = msg.payload
        self.schedule_update_ha_state(True)

    async def mute_listener(self, msg):
        self._is_mute = msg.payload == '1'
        self.schedule_update_ha_state(True)

    async def cover_listener(self, msg):
        _image = msg.payload.replace("\n","")
        if _image == 'none':
           self._cover = None

           self.schedule_update_ha_state(True)
           return

        _parsed = urlparse(_image)

        if _parsed.path != _image:
            _image = base64.b64encode(requests.get(_image).content)

        if len(_image) > 0:
            self._cover = base64.b64decode(_image)
        else:
            self._cover = None

        self.schedule_update_ha_state(True)

    async def icon_listener(self, msg):
        self._icon = msg.payload
        self.schedule_update_ha_state(True)

    def update_features(self, name):
        if name == VOLUME_TOPIC:
            self._features |= SUPPORT_VOLUME_SET
        if name == MUTE_TOPIC:
            self._features |= SUPPORT_VOLUME_MUTE
        if name == VOLUME_UP_TOPIC or name == VOLUME_DOWN_TOPIC:
            self._features |= SUPPORT_VOLUME_STEP
        if name == NEXT_TOPIC:
            self._features |= SUPPORT_NEXT_TRACK
        if name == PREV_TOPIC:
            self._features |= SUPPORT_PREVIOUS_TRACK
        if name == SOURCE_TOPIC:
            self._features |= SUPPORT_SELECT_SOURCE
        if name == SEEK_TOPIC:
            self._features |= SUPPORT_SEEK

    def update(self):
        return

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def media_duration(self):
        return self._duration

    @property
    def media_position(self):
        return self._position

    @property
    def media_position_updated_at(self):
        return self._position_updated_at

    @property
    def volume_level(self):
        if self._volume:
            return float(float(self._volume) / 100.0)

        return None

    @property
    def media_content_type(self):
        return self._type

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        return self._source_list

    @property
    def media_title(self):
        return self._title

    @property
    def media_artist(self):
        return self._artist

    @property
    def media_album_name(self):
        return self._album

    @property
    def app_name(self):
        return self._app

    @property
    def media_series_title(self):
        return self._series_title

    @property
    def media_season(self):
        return self._season

    @property
    def media_episode(self):
        return self._episode

    @property
    def supported_features(self):
        return self._features

    @property
    def media_image_hash(self):
        if self._cover:
            return hashlib.md5(self._cover).hexdigest()[:5]

        return None

    @property
    def is_volume_muted(self):
        return self._is_mute

    @property
    def icon(self):
        return self._icon

    async def async_get_media_image(self):
        if self._cover:
            return (self._cover, "image/jpeg")

        return None, None

    async def async_turn_on(self):
        if self._state == STATE_IDLE:
            await self.async_turn_off()

            return

        if self._publish_topics[STATE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STATE_TOPIC], STATE_ON)

        self._state = STATE_ON
        self.schedule_update_ha_state(True)

    async def async_turn_off(self):
        if self._publish_topics[STATE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STATE_TOPIC], STATE_OFF)

        self._state = STATE_OFF
        self.schedule_update_ha_state(True)

    async def async_volume_up(self):
        if self._disabled_in_state[VOLUME_UP_TOPIC] is not None and self._state in self._disabled_in_state[VOLUME_UP_TOPIC]:
            return

        if self._publish_topics[VOLUME_UP_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[VOLUME_UP_TOPIC], "+")
        else:
            self.set_volume_level(self._volume + 0.01)

    async def async_volume_down(self):
        if self._disabled_in_state[VOLUME_DOWN_TOPIC] is not None and self._state in self._disabled_in_state[VOLUME_DOWN_TOPIC]:
            return

        if self._publish_topics[VOLUME_DOWN_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[VOLUME_DOWN_TOPIC], "-")
        else:
            self.set_volume_level(self._volume - 0.01)

    async def async_set_volume_level(self, volume):
        if self._disabled_in_state[VOLUME_TOPIC] is not None and self._state in self._disabled_in_state[VOLUME_TOPIC]:
            return

        if self._publish_topics[VOLUME_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[VOLUME_TOPIC], int(volume * 100))

        self._volume = volume
        self.schedule_update_ha_state(True)

    async def async_mute_volume(self, mute):
        if self._disabled_in_state[MUTE_TOPIC] is not None and self._state in self._disabled_in_state[MUTE_TOPIC]:
            return

        if mute:
            self._prev_volume = self._volume
        elif self._prev_volume is not None:
            self.async_set_volume_level(self._prev_volume)

        if self._publish_topics[MUTE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[MUTE_TOPIC], 1 if mute else 0)

        self._is_mute = mute
        self.schedule_update_ha_state(True)

    async def async_media_play_pause(self):
        if self._state == STATE_PLAYING:
            await self.async_media_pause()
        else:
            await self.async_media_play()

    async def async_media_play(self):
        if self._publish_topics[STATE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STATE_TOPIC], STATE_PLAYING)

        self._state = STATE_PLAYING
        self.schedule_update_ha_state(True)

    async def async_media_pause(self):
        if self._publish_topics[STATE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STATE_TOPIC], STATE_PAUSED)

        self._state = STATE_PAUSED
        self.schedule_update_ha_state(True)

    async def async_media_stop(self):
        if self._disabled_in_state[STOP_TOPIC] is not None and self._state in self._disabled_in_state[STOP_TOPIC]:
            return

        if self._publish_topics[STOP_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[STOP_TOPIC], STATE_STOP)

            self._state = STATE_IDLE
            self.schedule_update_ha_state(True)
        else:
            await self.async_media_pause()

    async def async_media_next_track(self):
        if self._disabled_in_state[NEXT_TOPIC] is not None and self._state in self._disabled_in_state[NEXT_TOPIC]:
            return

        if self._publish_topics[NEXT_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[NEXT_TOPIC], STATE_NEXT)

    async def async_media_previous_track(self):
        if self._disabled_in_state[PREV_TOPIC] is not None and self._state in self._disabled_in_state[PREV_TOPIC]:
            return

        if self._publish_topics[PREV_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[PREV_TOPIC], STATE_PREV)

    async def async_select_source(self, source):
        if self._disabled_in_state[SOURCE_TOPIC] is not None and self._state in self._disabled_in_state[SOURCE_TOPIC]:
            return

        if self._publish_topics[SOURCE_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[SOURCE_TOPIC], source)

        self._source = source
        self.schedule_update_ha_state(True)

    async def async_media_seek(self, position):
        if self._disabled_in_state[SEEK_TOPIC] is not None and self._state in self._disabled_in_state[SEEK_TOPIC]:
            return

        if self._publish_topics[SEEK_TOPIC] is not None:
            mqtt.async_publish(self.hass, self._publish_topics[SEEK_TOPIC], position)

        self._position = position
        self.schedule_update_ha_state(True)
