from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os.path

from PIL import Image, ImageDraw, ImageFont
from math import floor

__here__ = os.path.dirname(__file__)

font_path = os.path.join(__here__, 'data', 'Arial.ttf')


class ImageRenderer(object):
    # TODO:
    # - Add a "drawndown only" option
    # - Add a default tag (like a small delta symbol) to signal the initial
    # shuttle direction
    # - Add option to render the backside of the fabric
    # - Add option to render a bar graph of the thread crossings along the
    # sides
    # - Add option to render 'stats table'
    #   - Number of warp threads
    #   - Number of weft threads
    #   - Number of harnesses/shafts
    #   - Number of treadles
    #   - Warp unit size / reps
    #   - Weft unit size / reps
    #   - Longest warp float
    #   - Longest weft float
    #   - Selvedge continuity
    # - Add option to rotate orientation
    # - Add option to render selvedge continuity
    # - Add option to render inset "scale view" rendering of fabric
    # - Add option to change thread spacing
    # - Support variable thickness threads
    # - Add option to render heddle count on each shaft
        
    
    def __init__(self, draft, style):
                 # liftplan=None, margin_pixels=20, scale=10,
                 # foreground=(127, 127, 127), background=(255, 255, 255),
                 # marker_color=(0, 0, 0), number_color=(200, 0, 0)):
        self.draft = draft
        self.style = style

        self.liftplan = None #!!liftplan is defined in the draft by wifreader

        self.border_pixels = style.border_pixels #border_pixels
        self.pixels_per_square = style.box_size #scale

        self.background = style.background #background
        self.outline_color = style.outline_color #foreground
        self.boxfill_color = style.boxfill_color #marker_color
        self.tick_color = style.tick_color_rgb #number_color

        self.tick_font_size = int(round(self.pixels_per_square * 1.2))
        self.thread_font_size = int(round(self.pixels_per_square * 0.8))

        self.tick_font = ImageFont.truetype(font_path, self.tick_font_size)
        self.thread_font = ImageFont.truetype(font_path, self.thread_font_size)

    def pad_image(self, im):
        w, h = im.size
        desired_w = w + (self.border_pixels * 2)
        desired_h = h + (self.border_pixels * 2)
        new = Image.new('RGB', (desired_w, desired_h), self.background.rgb)
        new.paste(im, (self.border_pixels, self.border_pixels))
        return new

    def make_pil_image(self):
        width_squares = len(self.draft.warp) + 6
        if self.liftplan or self.draft.liftplan:
            width_squares += len(self.draft.shafts)
        else:
            width_squares += len(self.draft.treadles)

        height_squares = len(self.draft.weft) + 6 + len(self.draft.shafts)

        # XXX Not totally sure why the +1 is needed here, but otherwise the
        # contents overflows the canvas
        width = (width_squares * self.pixels_per_square) + 1
        height = (height_squares * self.pixels_per_square) + 1

        im = Image.new('RGB', (width, height), self.background.rgb)

        draw = ImageDraw.Draw(im)

        self.paint_warp_colors(draw)
        self.paint_threading(draw)

        self.paint_weft(draw)
        if self.liftplan or self.draft.liftplan:
            self.paint_liftplan(draw)
        else:
            self.paint_tieup(draw)
            self.paint_treadling(draw)

        self.paint_drawdown(draw)
        self.paint_start_indicator(draw)
        del draw

        im = self.pad_image(im)
        return im

    def paint_start_indicator(self, draw):
        offsety = 0
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            offsety = self.style.tick_length
        offsety += self.style.warp_start + len(self.draft.shafts)+self.style.drawdown_gap
        offsety *= self.pixels_per_square
        starty = (offsety - (self.pixels_per_square // 2))
        
        if self.draft.start_at_lowest_thread:
            # right side
            endx = len(self.draft.warp) * self.pixels_per_square
            startx = endx - self.pixels_per_square
        else:
            # left side
            startx = 0
            endx = self.pixels_per_square
        vertices = [
            (startx, starty),
            (endx, starty),
            (startx + (self.pixels_per_square // 2), offsety),
        ]
        draw.polygon(vertices, fill=self.boxfill_color.rgb)

    def paint_warp_colors(self, draw):
        """ paint each thread as an outlined box, filled with thread color
        """
        starty = 0
        endy = self.pixels_per_square
        num_threads = len(self.draft.warp)
        
        for ii, thread in enumerate(self.draft.warp):
            startx = (num_threads - ii - 1) * self.pixels_per_square
            endx = startx + self.pixels_per_square
            draw.rectangle((startx, starty, endx, endy),
                           outline=self.outline_color.rgb,
                           fill=thread.color.rgb)

    def paint_fill_marker(self, draw, box, blobcolor, style, label=None, bgcolor=None):
        startx, starty, endx, endy = box
        # if bgcolor same as thread color then we have to override with a blob
        if bgcolor and bgcolor.close(self.style.background):
            style = 'blob'
            bgcolor = None
        margin = 1

        if bgcolor:
            draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                       fill=bgcolor.rgb)
        else: # Foreground (blob, solid)
            if style == 'blob' and not bgcolor:
                margin = floor((endx-startx)/5)
                draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                                fill=blobcolor.rgb)
            elif style == 'solid' and not bgcolor:
                draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                                fill=blobcolor.rgb)
        # Foreground (number,letter)
        if style == 'number' or style == 'XO': # lettter or number
            if style == 'number':
                # extract thread number, place text usin label
                pass
            else: # style = letter
                # choose X,O based on rising shed
                pass
            # Draw  text
            pass
            

    def paint_threading(self, draw):
        num_threads = len(self.draft.warp)
        num_shafts = len(self.draft.shafts)
        bgcolor = None
        start_tick_y = self.style.warp_start
        tick_length = self.style.tick_length #tick_gap
        end_tick = start_tick_y + tick_length
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            start_warp_y = start_tick_y + tick_length -1
        else:
            start_warp_y = start_tick_y -1
        

        for ii, thread in enumerate(self.draft.warp):
            startx = (num_threads - ii - 1) * self.pixels_per_square
            endx = startx + self.pixels_per_square
            if self.style.warp_use_thread_color:
                bgcolor = thread.color

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (start_warp_y + (num_shafts - jj)) * self.pixels_per_square
                endy = starty + self.pixels_per_square
                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft == thread.shaft:
                    # draw threading marker
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.warp_style, None,bgcolor)

            # paint tick, number if it's a multiple of tick_mod and not the first one
            if self.style.warp_tick_active:
                thread_no = ii + 1
                if ((thread_no != num_threads) and
                    (thread_no != 0) and
                        (thread_no % self.style.tick_mod == 0)):
                    # draw line
                    startx = endx = (num_threads - ii - 1) * self.pixels_per_square
                    starty = start_tick_y * self.pixels_per_square
                    endy = (end_tick * self.pixels_per_square) - 1
                    draw.line((startx, starty, endx, endy),
                              fill=self.tick_color)
                    # draw text
                    draw.text((startx + 2, starty + 2),
                              str(thread_no),
                              font=self.tick_font,
                              fill=self.tick_color)

    def paint_weft(self, draw):
        offsety = 0
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            offsety = self.style.tick_length
        offsety += self.style.warp_start + len(self.draft.shafts)+self.style.drawdown_gap
        offsety *= self.pixels_per_square
        
        offsetx = len(self.draft.warp) + self.style.drawdown_gap + self.style.tick_length + self.style.weft_gap
        if self.liftplan or self.draft.liftplan:
            offsetx += len(self.draft.shafts)
        else:
            offsetx += len(self.draft.treadles)
        startx = offsetx * self.pixels_per_square
        endx = startx + self.pixels_per_square

        for ii, thread in enumerate(self.draft.weft):
            # paint box, outlined with foreground color, filled with thread
            # color
            starty = (self.pixels_per_square * ii) + offsety
            endy = starty + self.pixels_per_square
            draw.rectangle((startx, starty, endx, endy),
                           outline=self.outline_color.rgb,
                           fill=thread.color.rgb)

    def paint_liftplan(self, draw):
        num_threads = len(self.draft.weft)
        bgcolor = None
        offsety = 0
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            offsety = self.style.tick_length
        offsety += self.style.warp_start + len(self.draft.shafts)+self.style.drawdown_gap
        offsety *= self.pixels_per_square
        offsetx = (self.style.drawdown_gap + len(self.draft.warp)) * self.pixels_per_square
        
        if self.style.weft_use_thread_color:
                bgcolor = thread.color
                
        for ii, thread in enumerate(self.draft.weft):
            starty = (ii * self.pixels_per_square) + offsety
            endy = starty + self.pixels_per_square

            for jj, shaft in enumerate(self.draft.shafts):
                startx = (jj * self.pixels_per_square) + offsetx
                endx = startx + self.pixels_per_square
                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft in thread.connected_shafts:
                    # draw liftplan marker
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.weft_style, None,bgcolor)

            # paint tick, number if it's a multiple of tick_mod and not the first one
            thread_no = ii + 1
            if ((thread_no != num_threads) and
                (thread_no != 0) and
                    (thread_no % self.style.tick_mod == 0)):
                # draw line
                startx = endx
                starty = endy
                endx = startx + (2 * self.pixels_per_square)
                endy = starty
                draw.line((startx, starty, endx, endy),
                          fill=self.tick_color)
                # draw text
                draw.text((startx + 2, starty - 2 - self.tick_font_size),
                          str(thread_no),
                          font=self.tick_font,
                          fill=self.tick_color)

    def paint_tieup(self, draw):
        offsetx = (self.style.drawdown_gap + len(self.draft.warp)) * self.pixels_per_square
        
        start_tick_y = self.style.warp_start
        tick_length = self.style.tick_length
        end_tick = start_tick_y + tick_length
        start_tieup_y = start_tick_y - 1
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            start_tieup_y += tick_length
        
        num_treadles = len(self.draft.treadles)
        num_shafts = len(self.draft.shafts)

        for ii, treadle in enumerate(self.draft.treadles):
            startx = (ii * self.pixels_per_square) + offsetx
            endx = startx + self.pixels_per_square

            treadle_no = ii + 1

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (num_shafts - jj + start_tieup_y) * self.pixels_per_square
                endy = starty + self.pixels_per_square

                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft in treadle.shafts:
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.tieup_style, None,None)

                # paint tick, number if it's a multiple of tick_mod and not the first one
                if self.style.tieup_tick_active:
                    if treadle_no == num_treadles:
                        shaft_no = jj + 1
                        if (shaft_no != 0) and (shaft_no % self.style.tick_mod == 0):
                            # draw line
                            line_startx = endx
                            line_endx = line_startx + (2 * self.pixels_per_square)
                            line_starty = line_endy = starty
                            draw.line((line_startx, line_starty,
                                       line_endx, line_endy),
                                      fill=self.tick_color)
                            draw.text((line_startx + 2, line_starty + 2),
                                      str(shaft_no),
                                      font=self.tick_font,
                                      fill=self.tick_color)
            
            # paint tick, number if it's a multiple of tick_mod and not the first one
            if self.style.tieup_tick_active:
                if (treadle_no != 0) and (treadle_no % self.style.tick_mod == 0):
                    # draw line
                    startx = endx = (treadle_no * self.pixels_per_square) + offsetx
                    starty = start_tick_y * self.pixels_per_square
                    endy = (end_tick * self.pixels_per_square) - 1
                    draw.line((startx, starty, endx, endy),
                              fill=self.tick_color)
                    # draw text on left side, right justified
                    textw, texth = draw.textsize(str(treadle_no), font=self.tick_font)
                    draw.text((startx - textw - 2, starty + 2),
                              str(treadle_no),
                              font=self.tick_font,
                              fill=self.tick_color)

    def paint_treadling(self, draw):
        num_threads = len(self.draft.weft)
        bgcolor = None
        
        offsety = 0
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            offsety = self.style.tick_length
        offsety += self.style.warp_start + len(self.draft.shafts)+self.style.drawdown_gap
        offsety *= self.pixels_per_square
        offsetx = (self.style.drawdown_gap + len(self.draft.warp)) * self.pixels_per_square
        #
        for ii, thread in enumerate(self.draft.weft):
            starty = (ii * self.pixels_per_square) + offsety
            endy = starty + self.pixels_per_square
            if self.style.weft_use_thread_color:
                bgcolor = thread.color

            for jj, treadle in enumerate(self.draft.treadles):
                startx = (jj * self.pixels_per_square) + offsetx
                endx = startx + self.pixels_per_square
                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if treadle in thread.treadles:
                    # draw treadling marker
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.weft_style, None,bgcolor)
            # paint tick, number if it's a multiple of tick_mod and not the first one
            if self.style.weft_tick_active:
                thread_no = ii + 1
                if ((thread_no != num_threads) and
                    (thread_no != 0) and
                        (thread_no % self.style.tick_mod == 0)):
                    # draw line
                    startx = endx
                    starty = endy
                    endx = startx + (2 * self.pixels_per_square)
                    endy = starty
                    draw.line((startx, starty, endx, endy),
                              fill=self.tick_color)
                    # draw text
                    draw.text((startx + 2, starty - 2 - self.tick_font_size),
                              str(thread_no),
                              font=self.tick_font,
                              fill=self.tick_color)

    def paint_drawdown(self, draw):
        num_threads = len(self.draft.warp)
        floats = self.draft.compute_floats()
        # drawdown styles = [solid | box | intersect | boxshaded | solidshaded]
        
        float_color = self.style.floats_color
        float_cutoff = self.style.floats_count
        show_float = self.style.show_floats
        
        offsety = 0
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            offsety = self.style.tick_length
        offsety += self.style.warp_start + len(self.draft.shafts)+self.style.drawdown_gap
        offsety *= self.pixels_per_square

        for start, end, visible, length, thread in floats:
            if visible:
                startx = (num_threads - end[0]-1) * self.pixels_per_square
                starty = (start[1] * self.pixels_per_square) + offsety
                endx = (num_threads - start[0]) * self.pixels_per_square
                endy = ((end[1] + 1) * self.pixels_per_square) + offsety
                outline_color = self.outline_color.rgb
                fill_color = thread.color.rgb
                if show_float and length >= float_cutoff:
                    outline_color = (255,255,255)
                    fill_color = float_color.rgb
                draw.rectangle((startx, starty, endx, endy),
                               outline=outline_color,
                               fill=fill_color)

    def show(self):
        im = self.make_pil_image()
        im.show()

    def save(self, filename):
        im = self.make_pil_image()
        im.save(filename)


svg_preamble = '<?xml version="1.0" encoding="utf-8" standalone="no"?>'
svg_header = '''<svg width="{width}" height="{height}"
    viewBox="0 0 {width} {height}"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink">'''


class TagGenerator(object):
    def __getattr__(self, name):
        def tag(*children, **attrs):
            inner = ''.join(children)
            if attrs:
                attrs = ' '.join(['%s="%s"' % (key.replace('_', '-'), val)
                                  for key, val in attrs.items()])
                return '<%s %s>%s</%s>' % (name, attrs, inner, name)
            else:
                return '<%s>%s</%s>' % (name, inner, name)
        return tag


SVG = TagGenerator()


class SVGRenderer(object):
    def __init__(self, draft, liftplan=None, scale=10,
                 foreground='#7f7f7f', background='#ffffff',
                 marker_color='#000000', number_color='#c80000'):
        self.draft = draft

        self.liftplan = liftplan

        self.scale = scale

        self.background = background
        self.outline_color = foreground
        self.marker_color = marker_color
        self.number_color = number_color

        self.font_family = 'Arial, sans-serif'
        self.tick_font_size = 12

    def make_svg_doc(self):
        width_squares = len(self.draft.warp) + 6
        if self.liftplan or self.draft.liftplan:
            width_squares += len(self.draft.shafts)
        else:
            width_squares += len(self.draft.treadles)

        height_squares = len(self.draft.weft) + 6 + len(self.draft.shafts)

        width = width_squares * self.scale
        height = height_squares * self.scale

        doc = []
        # Use a negative starting point so we don't have to offset everything
        # in the drawing.
        doc.append(svg_header.format(width=width, height=height))

        self.write_metadata(doc)

        self.paint_warp_colors(doc)
        self.paint_threading(doc)

        self.paint_weft(doc)
        if self.liftplan or self.draft.liftplan:
            self.paint_liftplan(doc)
        else:
            self.paint_tieup(doc)
            self.paint_treadling(doc)

        self.paint_drawdown(doc)
        doc.append('</svg>')
        return '\n'.join(doc)

    def write_metadata(self, doc):
        doc.append(SVG.title(self.draft.title))

    def paint_warp_colors(self, doc):
        starty = 0
        grp = []
        for ii, thread in enumerate(self.draft.warp):
            # paint box, outlined with foreground color, filled with thread
            # color
            startx = self.scale * ii
            grp.append(SVG.rect(
                x=startx, y=starty,
                width=self.scale, height=self.scale,
                style='stroke:%s; fill:%s' % (self.outline_color,
                                              thread.color.css)))
        doc.append(SVG.g(*grp))

    def paint_weft(self, doc):
        offsety = (6 + len(self.draft.shafts)) * self.scale
        startx_squares = len(self.draft.warp) + 5
        if self.liftplan or self.draft.liftplan:
            startx_squares += len(self.draft.shafts)
        else:
            startx_squares += len(self.draft.treadles)
        startx = startx_squares * self.scale

        grp = []
        for ii, thread in enumerate(self.draft.weft):
            # paint box, outlined with foreground color, filled with thread
            # color
            starty = (self.scale * ii) + offsety
            grp.append(SVG.rect(
                x=startx, y=starty,
                width=self.scale, height=self.scale,
                style='stroke:%s; fill:%s' % (self.outline_color,
                                              thread.color.css)))
        doc.append(SVG.g(*grp))

    def paint_fill_marker(self, doc, box):
        startx, starty, endx, endy = box
        # XXX FIXME make box setback generated from scale fraction
        assert self.scale > 8
        doc.append(SVG.rect(
            x=startx + 2,
            y=starty + 2,
            width=self.scale - 4,
            height=self.scale - 4,
            style='fill:%s' % self.marker_color))

    def paint_threading(self, doc):
        num_threads = len(self.draft.warp)
        num_shafts = len(self.draft.shafts)

        grp = []
        for ii, thread in enumerate(self.draft.warp):
            startx = (num_threads - ii - 1) * self.scale
            endx = startx + self.scale

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (4 + (num_shafts - jj)) * self.scale
                endy = starty + self.scale
                grp.append(SVG.rect(
                    x=startx, y=starty,
                    width=self.scale, height=self.scale,
                    style='stroke:%s; fill:%s' % (self.outline_color,
                                                  self.background)))

                if shaft == thread.shaft:
                    # draw threading marker
                    self.paint_fill_marker(grp, (startx, starty, endx, endy))

            # paint the number if it's a multiple of 4
            thread_no = ii + 1
            if ((thread_no != num_threads) and
                (thread_no != 0) and
                    (thread_no % 4 == 0)):
                # draw line
                startx = endx = (num_threads - ii - 1) * self.scale
                starty = 3 * self.scale
                endy = (5 * self.scale) - 1
                grp.append(SVG.line(
                    x1=startx,
                    y1=starty,
                    x2=endx,
                    y2=endy,
                    style='stroke:%s' % self.number_color))
                # draw text
                grp.append(SVG.text(
                    str(thread_no),
                    x=(startx + 3),
                    y=(starty + self.tick_font_size),
                    style='font-family:%s; font-size:%s; fill:%s' % (
                        self.font_family,
                        self.tick_font_size,
                        self.number_color)))
        doc.append(SVG.g(*grp))

    def paint_liftplan(self, doc):
        num_threads = len(self.draft.weft)

        offsetx = (1 + len(self.draft.warp)) * self.scale
        offsety = (6 + len(self.draft.shafts)) * self.scale

        grp = []
        for ii, thread in enumerate(self.draft.weft):
            starty = (ii * self.scale) + offsety
            endy = starty + self.scale

            for jj, shaft in enumerate(self.draft.shafts):
                startx = (jj * self.scale) + offsetx
                endx = startx + self.scale
                grp.append(SVG.rect(
                    x=startx,
                    y=starty,
                    width=self.scale,
                    height=self.scale,
                    style='stroke:%s; fill:%s' % (self.outline_color,
                                                  self.background)))

                if shaft in thread.connected_shafts:
                    # draw liftplan marker
                    self.paint_fill_marker(grp, (startx, starty, endx, endy))

            # paint the number if it's a multiple of 4
            thread_no = ii + 1
            if ((thread_no != num_threads) and
                (thread_no != 0) and
                    (thread_no % 4 == 0)):
                # draw line
                startx = endx
                starty = endy
                endx = startx + (2 * self.scale)
                endy = starty
                grp.append(SVG.line(
                    x1=startx,
                    y1=starty,
                    x2=endx,
                    y2=endy,
                    style='stroke:%s' % self.number_color))
                # draw text
                grp.append(SVG.text(
                    str(thread_no),
                    x=(startx + 3),
                    y=(starty - 4),
                    style='font-family:%s; font-size:%s; fill:%s' % (
                        self.font_family,
                        self.tick_font_size,
                        self.number_color)))
        doc.append(SVG.g(*grp))

    def paint_tieup(self, doc):
        offsetx = (1 + len(self.draft.warp)) * self.scale
        offsety = 5 * self.scale

        num_treadles = len(self.draft.treadles)
        num_shafts = len(self.draft.shafts)

        grp = []
        for ii, treadle in enumerate(self.draft.treadles):
            startx = (ii * self.scale) + offsetx
            endx = startx + self.scale

            treadle_no = ii + 1

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (((num_shafts - jj - 1) * self.scale) +
                          offsety)
                endy = starty + self.scale

                grp.append(SVG.rect(
                    x=startx,
                    y=starty,
                    width=self.scale,
                    height=self.scale,
                    style='stroke:%s; fill:%s' % (self.outline_color,
                                                  self.background)))

                if shaft in treadle.shafts:
                    self.paint_fill_marker(grp, (startx, starty, endx, endy))

                # on the last treadle, paint the shaft markers
                if treadle_no == num_treadles:
                    shaft_no = jj + 1
                    if (shaft_no != 0) and (shaft_no % 4 == 0):
                        # draw line
                        line_startx = endx
                        line_endx = line_startx + (2 * self.scale)
                        line_starty = line_endy = starty
                        grp.append(SVG.line(
                            x1=line_startx,
                            y1=line_starty,
                            x2=line_endx,
                            y2=line_endy,
                            style='stroke:%s' % self.number_color))
                        grp.append(SVG.text(
                            str(shaft_no),
                            x=(line_startx + 3),
                            y=(line_starty + 2 + self.tick_font_size),
                            style='font-family:%s; font-size:%s; fill:%s' % (
                                self.font_family,
                                self.tick_font_size,
                                self.number_color)))

            # paint the number if it's a multiple of 4 and not the first one
            if (treadle_no != 0) and (treadle_no % 4 == 0):
                # draw line
                startx = endx = (treadle_no * self.scale) + offsetx
                starty = 3 * self.scale
                endy = (5 * self.scale) - 1
                grp.append(SVG.line(
                    x1=startx,
                    y1=starty,
                    x2=endx,
                    y2=endy,
                    style='stroke:%s' % self.number_color))
                # draw text on left side, right justified
                grp.append(SVG.text(
                    str(treadle_no),
                    x=(startx - 3),
                    y=(starty + self.tick_font_size),
                    text_anchor='end',
                    style='font-family:%s; font-size:%s; fill:%s' % (
                        self.font_family,
                        self.tick_font_size,
                        self.number_color)))
        doc.append(SVG.g(*grp))

    def paint_treadling(self, doc):
        num_threads = len(self.draft.weft)

        offsetx = (1 + len(self.draft.warp)) * self.scale
        offsety = (6 + len(self.draft.shafts)) * self.scale

        grp = []
        for ii, thread in enumerate(self.draft.weft):
            starty = (ii * self.scale) + offsety
            endy = starty + self.scale

            for jj, treadle in enumerate(self.draft.treadles):
                startx = (jj * self.scale) + offsetx
                endx = startx + self.scale
                grp.append(SVG.rect(
                    x=startx,
                    y=starty,
                    width=self.scale,
                    height=self.scale,
                    style='stroke:%s; fill:%s' % (self.outline_color,
                                                  self.background)))

                if treadle in thread.treadles:
                    # draw treadling marker
                    self.paint_fill_marker(grp, (startx, starty, endx, endy))

            # paint the number if it's a multiple of 4
            thread_no = ii + 1
            if ((thread_no != num_threads) and
                (thread_no != 0) and
                    (thread_no % 4 == 0)):
                # draw line
                startx = endx
                starty = endy
                endx = startx + (2 * self.scale)
                endy = starty
                grp.append(SVG.line(
                    x1=startx,
                    y1=starty,
                    x2=endx,
                    y2=endy,
                    style='stroke:%s' % self.number_color))
                # draw text
                grp.append(SVG.text(
                    str(thread_no),
                    x=(startx + 3),
                    y=(starty - 4),
                    style='font-family:%s; font-size:%s; fill:%s' % (
                        self.font_family,
                        self.tick_font_size,
                        self.number_color)))
        doc.append(SVG.g(*grp))

    def paint_drawdown(self, doc):
        offsety = (6 + len(self.draft.shafts)) * self.scale
        floats = self.draft.compute_floats()

        grp = []
        for start, end, visible, length, thread in floats:
            if visible:
                startx = start[0] * self.scale
                starty = (start[1] * self.scale) + offsety
                endx = (end[0] + 1) * self.scale
                endy = ((end[1] + 1) * self.scale) + offsety
                width = endx - startx
                height = endy - starty
                grp.append(SVG.rect(
                    x=startx,
                    y=starty,
                    width=width,
                    height=height,
                    style='stroke:%s; fill:%s' % (self.outline_color,
                                                  thread.color.css)))
        doc.append(SVG.g(*grp))

    def render_to_string(self):
        return self.make_svg_doc()

    def save(self, filename):
        s = svg_preamble + '\n' + self.make_svg_doc()
        with open(filename, 'w') as f:
            f.write(s)
