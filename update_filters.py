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

import yaml
import ziproto
from sqlalchemy import Column, String, UnicodeText, Boolean, LargeBinary, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

try:
    CONFIG = yaml.load(open('config.yml', 'r'), Loader=yaml.SafeLoader)
except FileNotFoundError:
    print("Are you dumb? C'mon start using your brain!")
    quit(1)
except Exception as eee:
    print(
        f"Ah, look like there's error(s) while trying to load your config. It is\n!!!! ERROR BELOW !!!!\n {eee} \n !!! ERROR END !!!"
    )
    quit(1)

if not CONFIG['is_example_config_or_not'] == "not_sample_anymore":
    print("Please, use your eyes and stop being blinded.")
    quit(1)

def start() -> scoped_session:
    engine = create_engine(DB_URI, client_encoding="utf8")
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))

DB_URI = CONFIG['database_url']
BASE = declarative_base()
SESSION = start()

class OldCustomFilters(BASE):
    __tablename__ = "cust_filters"
    chat_id = Column(String(14), primary_key=True)
    keyword = Column(UnicodeText, primary_key=True, nullable=False)
    reply = Column(UnicodeText, nullable=False)
    is_sticker = Column(Boolean, nullable=False, default=False)
    is_document = Column(Boolean, nullable=False, default=False)
    is_image = Column(Boolean, nullable=False, default=False)
    is_audio = Column(Boolean, nullable=False, default=False)
    is_voice = Column(Boolean, nullable=False, default=False)
    is_video = Column(Boolean, nullable=False, default=False)

    has_buttons = Column(Boolean, nullable=False, default=False)
    # NOTE: Here for legacy purposes, to ensure older filters don't mess up.
    has_markdown = Column(Boolean, nullable=False, default=False)

    def __init__(self,
                 chat_id,
                 keyword,
                 reply,
                 is_sticker=False,
                 is_document=False,
                 is_image=False,
                 is_audio=False,
                 is_voice=False,
                 is_video=False,
                 has_buttons=False):
        self.chat_id = str(chat_id)  # ensure string
        self.keyword = keyword
        self.reply = reply
        self.is_sticker = is_sticker
        self.is_document = is_document
        self.is_image = is_image
        self.is_audio = is_audio
        self.is_voice = is_voice
        self.is_video = is_video
        self.has_buttons = has_buttons
        self.has_markdown = True

class FiltersObject(object):
    def __init__(self, data=None):
        self.data = {}
        if isinstance(data, bytes):
            self.data = ziproto.decode(data)

    def addFilter(self, keyword, response, response_type, has_buttons=False):
        self.data[keyword] = [
            response,
            response_type,
            has_buttons
        ]

class NewCustomFilters(BASE):
    __tablename__ = "blob_filters"
    chat_id = Column(String(14), primary_key=True)
    filters = Column(LargeBinary, nullable=True)

    def __init__(self, chat_id, filters):
        self.chat_id = str(chat_id)  # ensure string
        self.filters = filters

NewCustomFilters.__table__.create(checkfirst=True)

chats = SESSION.query(OldCustomFilters.chat_id).distinct().all()
for (chat_id, ) in chats:  # remove tuple by ( ,)
    filters_object = FiltersObject()
    all_filters = SESSION.query(OldCustomFilters).filter(OldCustomFilters.chat_id == chat_id).all()
    for i in all_filters:
        if i.is_sticker:
            response_type = 1
        elif i.is_document:
            response_type = 2
        elif i.is_image:
            response_type = 3
        elif i.is_audio:
            response_type = 4
        elif i.is_voice:
            response_type = 5
        elif i.is_video:
            response_type = 6
        else:
            response_type = 0
        filters_object.addFilter(i.keyword, i.reply, response_type, i.has_buttons)
    SESSION.add(NewCustomFilters(chat_id, ziproto.encode(filters_object.data)))
SESSION.commit()
