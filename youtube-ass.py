#!/usr/bin/env python
# -*- coding: utf-8 -*-

__authors__  = (
	'Nirbheek Chauhan',
	)

__license__ = 'Public Domain'
__version__ = '2012.01.12'

DEBUG = False

import xml.etree.ElementTree

class YoutubeAss(object):
    def __init__(self, string):
        """
        A class to convert Youtube XML annotations to ASS format
        http://en.wikipedia.org/wiki/SubStation_Alpha#Advanced_SubStation_Alpha

        Details about the ASS file format can be found at:
        * http://www.matroska.org/technical/specs/subtitles/ssa.html
        * http://moodub.free.fr/video/ass-specs.doc

        string: xml string containing the annotations
        """
        # Base screen size for placement calculations.
        # Everything scales according to these vs actual.
        # Font size and Shadow/Outline pixel widths apply to this screen size.
        self.width = 100
        self.height = 100
        self.xml = xml.etree.ElementTree.fromstring(string)
        # Subtitle events are a dict because annotation order is irrelevant
        self.events = {}
        self.styles = {}
        # Headers for each section of the ASS file
        # TODO: Add more Script Info
        self.Script_Info = "[Script Info]\n" \
        "ScriptType: V4.00+\nPlayResX: 100\nPlayResY: 100\n"
        self.V4_Styles = "[V4 Styles]\nFormat: Name, Fontname, Fontsize, " \
        "PrimaryColour, SecondaryColour, TertiaryColour, BackColour, Bold, " \
        "Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, " \
        "MarginV, AlphaLevel, Encoding\n"
        self.Events = "[Events]\nFormat: Marked, Start, End, Style, Name, " \
        "MarginL, MarginR, MarginV, Effect, Text\n"
        self._parse_xml()
        self._convert_to_ass()

    def _get_pos(self, x, y, w, h):
        """
        Since ASS can't place text in (x, y), we need to emulate that with
        alignments and margins. To make things worse, vertical margins are
        always from the closest screen edge.

        `MarginL` is the left margin
        `MarginR` is the right margin
        `MarginV` is the vertical margin from the closest edge (how silly)

        The 9 `Alignment`s on the screen are like this:
         _____
        |7 8 9|
        |4 5 6|
        |1 2 3|
         ¯¯¯¯¯
        Origin for input data is in the top left corner.
        x, y: coordinates of upper left corner of text box
        w, h: width and height of text box

        returns: (Alignment, (MarginL, MarginR, MarginV))
        """
        margins = (x, self.width - x - w)
        if y < self.height//2:
            # Toptitle, MarginV is from top
            margins += (y,)
            if x < self.width//2:
                return (7, margins)
            elif x > self.width//2:
                return (9, margins)
            else:
                return (8, margins)
        elif y > self.height//2:
            # Subtitle, MarginV is from bottom.
            margins += (self.height - y - h,)
            if x < self.width//2:
                return (1, margins)
            elif x > self.width//2:
                return (3, margins)
            else:
                return (2, margins)
        else:
            # Midtitle, MarginV is ignored here.
            margins += (0,)
            if x < self.width//2:
                return (4, margins)
            elif x > self.width//2:
                return (6, margins)
            else:
                return (5, margins)

    def _parse_xml(self):
        """
        Convert the input annotations XML into separate dicts for
        events (text + duration) and styles to be applied to those events.
        """
        for each in self.xml.find('annotations').findall('annotation'):
            # We use annotation ids as dict keys to match events with styles
            ant_id = each.get('id')
            if each.get('type') != "text":
                print("Skipping non-text annotation with id: "+ant_id)
                continue
            if not hasattr(each.find('TEXT'), "text"):
                print("Skipping empty annotation with id: "+ant_id)
                continue
            text = each.find('TEXT').text.encode('utf-8')
            moving_region = each.find('segment').find('movingRegion')
            box = moving_region.findall('rectRegion')
            if not box:
                box = moving_region.findall('anchoredRegion')
            if not box:
                print("No known regions inside <movingRegion>? Skipping...")
                continue
            # Make sure the order is preserved
            t1 = min(box[0].get('t'), box[1].get('t'))
            t2 = max(box[0].get('t'), box[1].get('t'))
            if "never" in (t1, t2):
                print("Found annotation that shouldn't be shown, skipping...")
                continue
            # Extract box dimensions and position
            (x, y, w, h) = map(float, (box[0].get(i) for i in ('x','y','w','h')))
            # Convert text box position to ASS title position
            (align, margins) = self._get_pos(x, y, w, h)
            if each.find('appearance') is not None:
                # Font colour
                fgColor = each.find('appearance').get('fgColor')
                # TODO: convert this into an ABGR box using Picture event lines
                # so that it matches the youtube annotations view.
                # BackColour is the "Outline" of the text, not exactly what we want
                bgColor = each.find('appearance').get('bgColor')
            else:
                # There's no colour, let's use black/white
                fgColor = '1'
                bgColor = '0'
            self.events.update({
                ant_id: {"Text": text, "Start": t1, "End": t2},
            })
            self.styles.update({
                ant_id: {"PrimaryColour": fgColor, "BackColour": bgColor,
                         "Alignment": align, "MarginL": margins[0],
                         "MarginR": margins[1], "MarginV": margins[2],},
            })

    def _convert_to_ass(self):
        self._write_styles()
        self._write_events()

    def _write_styles(self):
        """
        Write out the style information to self.V4_Styles

        Notes:
        `Fontsize`, `Outline`, `Shadow` closely match self.{width,height}
        AFAICT, youtube annotations cannot be `Bold` or `Italics`
        `BorderStyle`=1 is `Outline` + `Shadow`

        TODO: figure out `Encoding` parameter (0 is ANSI English)
        """
        misc_data = {
            "Fontname": "Arial", "Fontsize": "4.5", "Bold": "0",
            "Italic": "0", "BorderStyle": "1", "Outline": "0.1", "Shadow": "0.2",
            "Encoding": "0",
        }
        for (name, data) in self.styles.items():
            data.update(misc_data)
            line = "Style: {Name},{Fontname},{Fontsize},{PrimaryColour}," \
            "{PrimaryColour},{PrimaryColour},{BackColour},{Bold}," \
            "{Italic},{BorderStyle},{Outline},{Shadow},{Alignment}," \
            "{MarginL},{MarginR},{MarginV},0,{Encoding}" \
            "\n".format(Name=name, **data)
            self.V4_Styles += line

    def _write_events(self):
        """
        Write out subtitle event information to self.Events

        Notes:
        """
        misc_data = {
            "Marked": "Marked=0", "Name": "Speaker", "MarginL": "0",
            "MarginR": "0", "MarginV": "0", "Effect": "",
        }
        for (name, data) in self.events.items():
            data.update(misc_data)
            line = "Dialogue: {Marked},{Start},{End},{Style}," \
            "{Name},{MarginL},{MarginR},{MarginV},{Effect},{Text}" \
            "\n".format(Style=name, **data)
            self.Events += line

    def save(self, filename):
        with open(filename, 'w') as f:
            f.write(self.Script_Info)
            f.write("\n")
            f.write(self.V4_Styles)
            f.write("\n")
            f.write(self.Events)
            f.write("\n")

if __name__ == "__main__":
    import sys
    try:
        from urllib2 import urlopen
    except ImportError:
        from urllib.request import urlopen
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print("Usage: {0} <youtube video id>".format(sys.argv[0]))
        exit(0)
    video_id = sys.argv[1]
    url = "http://youtube.com/annotations/read2?feat=TCS&video_id=" + video_id
    xml_data = urlopen(url).read()
    if DEBUG:
        with open(video_id+'-annotations.xml', 'w') as f:
            f.write(str(xml_data))
    ass = YoutubeAss(xml_data)
    ass.save("{0}.ass".format(video_id))

# vim: set ts=4 sw=4 sts=4 noet ai si filetype=python:
