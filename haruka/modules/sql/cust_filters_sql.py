#    Haruka Aya (A telegram bot project)
#    Copyright (C) 2017-2019 Paul Larsen
#    Copyright (C) 2019-2020 Akito Mizukito (Haruka Network Development)

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import threading
import struct

struct.decode = struct.unpack  # Monkeypatch for ZiProto

import ziproto

from sqlalchemy import Column, String, UnicodeText, Boolean, Integer, LargeBinary, distinct, func

from haruka.modules.sql import BASE, SESSION


class FiltersObject(object):

    def __init__(self, data=None):
        self.data = {}
        if type(data) is bytes:
            self.data = ziproto.decode(data)

    def getAllKeywords(self):
        return self.data.keys()

    def getFilter(self, keyword, as_object=False):
        if keyword in self.data:
            if as_object:
                datum = self.data[keyword]
                return FilterObject(
                    keyword=keyword,
                    reply=datum[0],
                    reply_type=datum[1],
                    has_buttons=datum[2]
                )
            return self.data[keyword]

    def addFilter(self, keyword, response, response_type, has_buttons=False):
        self.data[keyword] = [
            response,
            response_type,
            has_buttons
        ]


class FilterObject(object):

    def __init__(self, keyword, reply, reply_type, has_buttons):
        self.keyword = keyword
        self.reply = reply
        self.reply_type = reply_type
        self.has_buttons = has_buttons

        self.is_text = False
        self.is_sticker = False
        self.is_document = False
        self.is_image = False
        self.is_audio = False
        self.is_voice = False
        self.is_video = False

        self.update()

    def update(self):
        if get_value_type(self.reply_type) == "text":
            self.is_text = True
        else:
            self.is_text = False

        if get_value_type(self.reply_type) == "sticker":
            self.is_sticker = True
        else:
            self.is_sticker = False

        if get_value_type(self.reply_type) == "document":
            self.is_document = True
        else:
            self.is_document = False

        if get_value_type(self.reply_type) == "image":
            self.is_image = True
        else:
            self.is_image = False

        if get_value_type(self.reply_type) == "audio":
            self.is_audio = True
        else:
            self.is_audio = False

        if get_value_type(self.reply_type) == "voice":
            self.is_voice = True
        else:
            self.is_voice = False

        if get_value_type(self.reply_type) == "video":
            self.is_video = True
        else:
            self.is_video = False


class CustomFilters(BASE):
    __tablename__ = "blob_filters"
    chat_id = Column(String(14), primary_key=True)
    filters = Column(LargeBinary, nullable=True)

    def __init__(self, chat_id, filters):
        self.chat_id = str(chat_id)  # ensure string
        self.filters = filters

    def __repr__(self):
        return "<Permissions for %s>" % self.chat_id


class Buttons(BASE):
    __tablename__ = "cust_filter_urls"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    url = Column(UnicodeText, nullable=False)
    same_line = Column(Boolean, default=False)

    def __init__(self, chat_id, keyword, name, url, same_line=False):
        self.chat_id = str(chat_id)
        self.keyword = keyword
        self.name = name
        self.url = url
        self.same_line = same_line


CustomFilters.__table__.create(checkfirst=True)
Buttons.__table__.create(checkfirst=True)

CUST_FILT_LOCK = threading.RLock()
BUTTON_LOCK = threading.RLock()
CHAT_FILTERS = {}


def get_value_type(value_int):
    types = {
        0: "text",
        1: "sticker",
        2: "document",
        3: "image",
        4: "audio",
        5: "voice",
        6: "video"
    }
    return types[value_int]


def get_all_filters():
    try:
        return SESSION.query(CustomFilters).all()
    finally:
        SESSION.close()


def add_filter(chat_id, keyword, reply, reply_type, buttons=None):
    global CHAT_FILTERS

    if buttons is None:
        buttons = []

    with CUST_FILT_LOCK:
        prev = SESSION.query(CustomFilters).get(str(chat_id))
        filters_data = FiltersObject()
        if prev:
            filters_data = FiltersObject(prev.filters)
            with BUTTON_LOCK:
                prev_buttons = SESSION.query(Buttons).filter(
                    Buttons.chat_id == str(chat_id),
                    Buttons.keyword == keyword).all()
                for btn in prev_buttons:
                    SESSION.delete(btn)

        filters_data.addFilter(
            keyword=keyword,
            response=reply,
            response_type=reply_type,
            has_buttons=False)

        if keyword not in CHAT_FILTERS.get(str(chat_id), []):
            CHAT_FILTERS[str(chat_id)] = sorted(
                CHAT_FILTERS.get(str(chat_id), []) + [keyword],
                key=lambda x: (-len(x), x))

        if prev:
            prev.filters = ziproto.encode(filters_data.data)
        else:
            filter_obj = CustomFilters(str(chat_id), ziproto.encode(filters_data.data))
            SESSION.add(filter_obj)
        SESSION.commit()

    for b_name, url, same_line in buttons:
        add_note_button_to_db(chat_id, keyword, b_name, url, same_line)


def remove_filter(chat_id, keyword):
    global CHAT_FILTERS
    with CUST_FILT_LOCK:
        filt = SESSION.query(CustomFilters).get((str(chat_id)))
        if filt:
            filters_object = FiltersObject(filt.filters)
            if keyword in CHAT_FILTERS.get(str(chat_id), []):  # Sanity check
                CHAT_FILTERS.get(str(chat_id), []).remove(keyword)
            if keyword in filters_object.data:
                filters_object.data.pop(keyword)
                filt.filters = ziproto.encode(filters_object.data)

            with BUTTON_LOCK:
                prev_buttons = SESSION.query(Buttons).filter(
                    Buttons.chat_id == str(chat_id),
                    Buttons.keyword == keyword).all()
                for btn in prev_buttons:
                    SESSION.delete(btn)

            SESSION.commit()
            return True

        SESSION.close()
        return False


def get_chat_triggers(chat_id):
    return CHAT_FILTERS.get(str(chat_id), set())


def get_filter(chat_id, keyword, as_object=False):
    try:
        results = SESSION.query(CustomFilters).get((str(chat_id)))
        return FiltersObject(results.filters).getFilter(keyword, as_object)
    finally:
        SESSION.close()


def add_note_button_to_db(chat_id, keyword, b_name, url, same_line):
    with BUTTON_LOCK:
        button = Buttons(chat_id, keyword, b_name, url, same_line)
        SESSION.add(button)
        SESSION.commit()


def get_buttons(chat_id, keyword):
    try:
        return SESSION.query(Buttons).filter(
            Buttons.chat_id == str(chat_id),
            Buttons.keyword == keyword).order_by(Buttons.id).all()
    finally:
        SESSION.close()


def num_filters():
    try:
        return SESSION.query(CustomFilters).count()
    finally:
        SESSION.close()


def num_chats():
    try:
        return SESSION.query(func.count(distinct(
            CustomFilters.chat_id))).scalar()
    finally:
        SESSION.close()


def __load_chat_filters():
    global CHAT_FILTERS
    try:
        chats = SESSION.query(CustomFilters.chat_id).distinct().all()
        for (chat_id,) in chats:  # remove tuple by ( ,)
            CHAT_FILTERS[chat_id] = []

        all_filters = SESSION.query(CustomFilters).all()
        for x in all_filters:
            filters_object = FiltersObject(x.filters)
            CHAT_FILTERS[x.chat_id] = filters_object.getAllKeywords()

        CHAT_FILTERS = {
            x: sorted(set(y), key=lambda i: (-len(i), i))
            for x, y in CHAT_FILTERS.items()
        }

    finally:
        SESSION.close()


def migrate_chat(old_chat_id, new_chat_id):
    with CUST_FILT_LOCK:
        chat_filters = SESSION.query(CustomFilters).filter(
            CustomFilters.chat_id == str(old_chat_id)).all()
        for filt in chat_filters:
            filt.chat_id = str(new_chat_id)
        SESSION.commit()
        CHAT_FILTERS[str(new_chat_id)] = CHAT_FILTERS[str(old_chat_id)]
        del CHAT_FILTERS[str(old_chat_id)]

        with BUTTON_LOCK:
            chat_buttons = SESSION.query(Buttons).filter(
                Buttons.chat_id == str(old_chat_id)).all()
            for btn in chat_buttons:
                btn.chat_id = str(new_chat_id)
            SESSION.commit()


__load_chat_filters()
