# coding: utf-8

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pyPdf, io, re
import socket, ssl
import sys, argparse, time
from urllib import urlopen
from html2text import html2text
import datetime

class Menu:
    def __init__(self, get_menu_func, url):
        self.url = url
        self.get_menu_func = get_menu_func

    def get_content(self):
        return self.get_menu_func (self.url)

    @staticmethod
    def process_menu_lines (lines, start, end):
        result = []
        processing_result = False

        for line in lines:
            low_line =line.lower()
            if start in low_line:
                processing_result = True
                result = []
                continue
            elif end in low_line or len(result) > 7:
                processing_result = False

            line = line.strip()
            if (processing_result and len(line) > 0):
                if len(result)>0 and len(line)<8:
                    # assume price or something similar
                    result[-1] = result[-1] + " " +line
                else:
                    result.append (line)

        return result

    @classmethod
    def get_content_by_date (cls, url):
        lines = Menu.get_lines(url)

        today = datetime.date.today()
        today_str = today.strftime("%-d.%-m.")
        tomorrow = today + datetime.timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%-d.%-m.")

        return cls.process_menu_lines (lines, today_str, tomorrow_str)

    @classmethod
    def get_content_by_weekday (cls, url):
        lines = Menu.get_lines(url)

        today = datetime.date.today()
        today_str = Menu.get_weekday(today)
        tomorrow = today + datetime.timedelta(days=1)
        tomorrow_str = Menu.get_weekday(tomorrow)

        return cls.process_menu_lines (lines, today_str, tomorrow_str)

    @staticmethod
    def get_lines (url):
        try:
            html = urlopen(url).read()
            # make random guesses on the document coding
            try:
                text = html2text(html.decode("utf-8"))
            except Exception:
                text = html2text(html.decode("latin-1", "ignore"))

            # workaround a html2text bug
            text = text.replace("&nbsp_place_holder;", " ");
            return text.split("\n")
        except Exception, err:
            print "Failed to get lines: %s" % err
            return []

    @staticmethod
    def get_weekday (date):
        weekday = date.strftime ("%w")
        if weekday == "0":
            return "sunnuntai"
        elif weekday == "1":
            return "maanantai"
        elif weekday == "2":
            return "tiistai"
        elif weekday == "3":
            return "keskiviikko"
        elif weekday == "4":
            return "torstai"
        elif weekday == "5":
            return "perjantai"
        return "lauantai"


class Restaurant:
    def __init__(self, name, menus):
        self.name = name
        self.menus = menus

    def get_menu (self):
        menu_lines = []
        for menu_obj in self.menus:
            menu_lines = menu_obj.get_content()
            if len(menu_lines) > 0:
                break
        return menu_lines


def send_menu (name, menu_lines):
    if len(menu_lines) == 0:
        ircsock.send ("PRIVMSG %s : %s: No menu for today :(\n" % (channel, name))
    elif len(menu_lines) == 1:
        ircsock.send ("PRIVMSG %s : %s: %s\n" % (channel, name, menu_lines[0].encode("utf-8")))
    else:
        ircsock.send ("PRIVMSG %s : %s:\n" % (channel, name))
        for line in menu_lines:
            ircsock.send ("PRIVMSG %s : | %s\n" % (channel, line.encode("utf-8")))

def handle_cmd_list (nick):
    if len(restaurants) > 0:
        output = restaurants[0].name
        for r in restaurants[1:]:
            output = output + ", " + r.name
        ircsock.send ("PRIVMSG %s : %s\n" % (channel, output))

def handle_cmd_menu (nick, options):
    if options:
        keywords = options.lower().split(None)
        match = False

        for keyword in keywords:
            for r in restaurants:
                if keyword in r.name.lower():
                    menu_lines = r.get_menu()
                    send_menu (r.name, menu_lines)
                    match = True

        if not match:
            ircsock.send ("PRIVMSG %s : No such restaurant '%s'\n" % (channel, options))
    else:
        for r in restaurants:
            menu_lines = r.get_menu()
            send_menu (r.name, menu_lines)

def handle_commands (nick, message):
    if message.startswith("menu"):
        params = None
        try:
            [cmd, params] = message.split(None, 1)
        except ValueError:
            pass
        handle_cmd_menu(nick, params)
    elif message.startswith("list"):
        handle_cmd_list(nick)
    else:
        ircsock.send("PRIVMSG %s :%s: try 'menu [<restaurant>]' or 'list'\n" % (channel, nick))


def get_blue_peter_content (url):
    try:
        today = datetime.date.today()

        html = urlopen(url).read()
        btn = html.index ("btnlounaslista.gif")
        end = html[:btn].rindex ("pdf") + 3
        start = html[:end].rindex ("http://")
        pdf_url = html[start:end]
        print pdf_url

        pdf_raw_data = urlopen(pdf_url).read()

        pdf = pyPdf.PdfFileReader(io.BytesIO(pdf_raw_data))
        pdf_text = pdf.pages[0].extractText()
        pdf_text = re.sub("Liikelounasmenu ", '', pdf_text)

        delimiters = "MAANANTAI|TIISTAI|KESKIVIIKKO|TORSTAI|PERJANTAI|VL ="
        return [re.split(delimiters, pdf_text)[datetime.date.weekday(today) + 1]]
    except ValueError:
        print "Failed to find Blue peter pdf";
        return []

def get_toro_content (url):
    return [Menu.get_content_by_weekday (url)[0]]

restaurants = [
    Restaurant ("Kylä",
                [Menu (Menu.get_content_by_date, "http://www.tapiolankyla.fi")]),
    Restaurant ("Luomumamas",
                [Menu (Menu.get_content_by_date, "http://www.sisdeli.fi/weegee-lounas.php"),
                 Menu (Menu.get_content_by_date, "http://weegee.fi/fi-FI/Palvelut/Ravintola_ja_catering_/SIS_DeliCafn_lounaslista(21617)")]),
    Restaurant ("Sumo",
                [Menu (Menu.get_content_by_weekday, "http://www.ravintolasumo.fi/lounas.html")]),
    Restaurant ("Ukkohauki",
                [Menu (Menu.get_content_by_date, "http://www.ravintolaukkohauki.fi/index.php?page=1008&lang=1")]),
    Restaurant ("Keilaranta",
                [Menu (Menu.get_content_by_weekday, "http://www.ravintolakeilaranta.fi/pages/lounaslista.php")]),
    Restaurant ("Blue Peter",
                [Menu (get_blue_peter_content, "http://www.bluepeter.fi/articles/292/")]),
    Restaurant ("Toro",
                [Menu (get_toro_content, "http://www.grillitoro.fi/lounas.html")]),
]

# Default argument values for testing
botnick = "lunchbot"
server = "irc.gnome.org"
port = 6667
channel = "#lunchbottest"
use_ssl = False

parser = argparse.ArgumentParser(description='Lunch bot for IRC.')
parser.add_argument('-n', '--nick', help='Bot nickname')
parser.add_argument('-s', '--server', help='IRC server address')
parser.add_argument('-p', '--port', type=int, help='IRC server port')
parser.add_argument('--ssl', action="store_true", help='Use SSL')
parser.add_argument('-c', '--channel', help='IRC channel to join')
parser.add_argument('-d', '--debug', action="store_true", help='Print more debug output')
args = parser.parse_args()

if args.nick:
    botnick = args.nick
if args.server:
    server = args.server
if args.port:
    port = args.port
if args.channel:
    channel = args.channel
use_ssl = args.ssl
debug = args.debug


# Industrial strength main loop
while True:
    try:
        ## Setup IRC socket, connect:

        ircsock = None
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout (60 * 6)
        s.connect((server, port))
        if use_ssl:
            ircsock = ssl.wrap_socket (s)
        else:
            ircsock = s

        ircsock.send("USER "+ botnick +" "+ botnick +" "+ botnick + " Lunch bot\n")
        ircsock.send("NICK "+ botnick +"\n")

        # Start listening for commands
        while True:
            # Block here until we have data (or timeout)
            lines = ircsock.recv(2048)
            if len(lines) == 0:
                print "Disconnected"
                break

            for ircmsg in lines.split('\r\n'):
                ircmsg = ircmsg.strip(' ')

                if (len(ircmsg) == 0):
                    continue

                if debug:
                    print ("DEBUG: " + ircmsg)

                if ircmsg.startswith("PING "):
                    ircsock.send("PONG %s\n" % botnick)
                    continue

                try:
                    [sender, cmd] = ircmsg.split (None, 1)

                    if cmd.startswith ("376 " + botnick):
                        # end of MOTD, joining should be ok now
                        ircsock.send("JOIN "+ channel +"\n")

                    elif cmd.startswith ("PRIVMSG"):
                        [privmsg, target, msg] = cmd.split (None, 2)
                        if msg.startswith(":" + botnick):
                            nick=sender.split ('!',1)[0][1:]
                            bot_cmd = msg.split (None,1)[1]
                            print("CMD (%s): %s" % (nick, bot_cmd))
                            handle_commands (nick, bot_cmd)
                        elif "Luomumamas: Ei lounasta." in msg:
                            nick=sender.split ('!',1)[0][1:]
                            handle_commands (nick, "menu mamas")

                except ValueError:
                    continue

        # Disconnecting
        break;

    except socket.timeout:
        print "Socket timed out, re-connecting right away..."
    except socket.error, err:
        # e.g. gethostbyname error
        print "Socket error: %s. Retrying after 60s..." % err
        time.sleep (60)
