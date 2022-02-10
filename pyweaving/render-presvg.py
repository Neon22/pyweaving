from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os.path

from PIL import Image, ImageDraw, ImageFont
from math import floor
from . import get_project_root, WHITE, BLACK

homedir = get_project_root()
font_path = os.path.join(homedir, 'data','Arial.ttf')


class ImageRenderer(object):
    # TODO:
    # - Add a "drawndown only" option
    # - Add a default tag (like a small delta symbol) to signal the initial
    # shuttle direction
    # - Add option to render the backside of the fabric
    # - Add option to render a bar graph of the thread crossings along the
    # sides
    # - Add option to render 'stats table'
    #   - Warp unit size / reps
    #   - Weft unit size / reps
    #   - Selvedge continuity
    # - Add option to rotate orientation
    # - Add option to render selvedge continuity
    # - Add option to render inset "scale view" rendering of fabric
    # - Support variable thickness threads

        
    
    def __init__(self, draft, style, show_liftplan=False):
        
        self.draft = draft
        self.style = style

        self.show_liftplan = show_liftplan #force liftplan display

        self.border_pixels = style.border_pixels
        self.pixels_per_square = style.box_size

        self.background = style.background
        self.outline_color = style.outline_color
        self.boxfill_color = style.boxfill_color
        self.tick_color = style.tick_color_rgb

        self.tick_font_size = int(round(self.pixels_per_square * 1.2))
        self.thread_font_size = int(round(self.pixels_per_square * 0.8))
        self.title_font_size = int(round(self.pixels_per_square * self.style.title_font_size_factor))

        self.tick_font = ImageFont.truetype(font_path, self.tick_font_size)
        self.thread_font = ImageFont.truetype(font_path, self.thread_font_size)
        self.title_font = ImageFont.truetype(font_path, self.title_font_size)

    def calculate_box_sizing(self):
        """ Store the yarn width on each thread,
             calculated from spacings data, on each thread.
        """
        all_spacings = self.draft.thread_stats["summary"]
        basicbox = self.style.box_size
        clarity_factor = self.style.clarity_factor
        
        sizing = []
        if all_spacings:
            # determine the ratios of the boxes for each mentioned 'spacing'
            ratios = [b/all_spacings[0] for b in all_spacings]
            for i,r in enumerate(ratios):
                if self.style.spacing_style == "clarity":
                    sizing.append([all_spacings[i],basicbox  + (i*clarity_factor*basicbox)])
                else: # "accuracy"
                    sizing.append([all_spacings[i],all_spacings[i]*basicbox])
                    # turn off some style that there is no room for (ugly)
                    self.style.disable_tickmarks()
                    self.style.set_warp_weft_style("solid")
                    # self.style.disable_thread_color()

        # store this info in all the threads for easy rendering later (thread.yarn_width)
        if sizing:
            for thread in self.draft.warp:
                spacing = thread.spacing
                for (s,dist) in sizing:
                    if s == spacing:
                        thread.yarn_width = dist
                        break # stop looking
            for thread in self.draft.weft:
                spacing = thread.spacing
                for (s,dist) in sizing:
                    if s == spacing:
                        thread.yarn_width = dist
                        break # stop looking
        return sizing
                    
        
        
    def pad_image(self, im):
        """ Final image has border added by pasting image into a larger one
        """
        w, h = im.size
        desired_w = w + (self.border_pixels * 2)
        desired_h = h + (self.border_pixels * 2)
        new = Image.new('RGB', (desired_w, desired_h), self.background.rgb)
        new.paste(im, (self.border_pixels, self.border_pixels))
        return new

    def make_pil_image(self):
        """ Determine size of components,
             make image,
             layout each part and draw them,
             add a border round the outside.
        """
        # gather spacings data for use in stats and to calc yarn widths to draw
        box_sizing = self.calculate_box_sizing() # incorporate spacing
        # calculate image size estimate (yarn spacing makes this a maximal number)
        warp_area_length = 0
        if box_sizing: # spacing data in wif file
            for spacing,count in self.draft.thread_stats["warp_spacings"]:
                distance = 0
                for (s,dist) in box_sizing:
                    if s == spacing:
                        distance = dist*count
                        break # stop looking
                warp_area_length += distance
            warp_area_length = int(warp_area_length / self.style.box_size) # distance in box units
        else: # no spacing data
            warp_area_length = len(self.draft.warp)
        # heddles
        warp_area_length += 2
        # gather width sizes
        width_squares_estimate = warp_area_length + 1 + self.style.tick_length + self.style.weft_gap  + self.style.drawdown_gap
        if self.show_liftplan or self.draft.liftplan:
            width_squares_estimate += len(self.draft.shafts)
        else:
            width_squares_estimate += len(self.draft.treadles)

        weft_area_length = 0
        if box_sizing:
            for spacing,count in self.draft.thread_stats["weft_spacings"]:
                distance = 0
                for s,dist in box_sizing:
                    if s == spacing:
                        distance = dist*count
                        break # stop looking
                weft_area_length += distance
            weft_area_length = int(weft_area_length / self.pixels_per_square) # distance in box units
        else: # no spacing data
            weft_area_length = len(self.draft.weft)
        height_squares_estimate = weft_area_length + len(self.draft.shafts) + \
                                  self.style.warp_gap  + self.style.drawdown_gap + \
                                  len(self.draft.draft_title) * 2 + 1 +self.style.tick_length
        # mini stats
        stats = self.draft.get_mini_stats()
        height_squares_estimate += int((len(stats) * self.tick_font_size * 1.5) / self.pixels_per_square) #(spacing)

        # Notes
        if self.draft.collected_notes:
            notes_size = len(self.draft.collected_notes) +2  #!! should be 1. Error somewhere else?
            height_squares_estimate += int((notes_size * self.tick_font_size * 1.5) / self.pixels_per_square)
            
        # outline width of +1 is added otherwise contents overflow
        width = width_squares_estimate * self.pixels_per_square + 1
        height = height_squares_estimate * self.pixels_per_square + 1
        startpos = (0,0) # in squares
        
        im = Image.new('RGB', (width, height), self.background.rgb)
        draw = ImageDraw.Draw(im)
        
        # Layout
        titlestart = startpos
        titleend = self.paint_title(titlestart, draw, self.draft.draft_title)
        ministatsend = self.paint_ministats((titlestart[0],titleend[1]), stats, draw)
        
        warpstart = [startpos[0], ministatsend[1]]
        warpstart[0] += 2 # heddlestats
        warpend = self.paint_warp_colors(warpstart, draw)
        warpstart[0] -= 2 # heddlestats
        
        heddlestart = (warpstart[0], warpend[1]+self.style.warp_gap)
        heddleend = self.paint_heddles_stats(heddlestart, draw)
        
        threadingstart = (heddleend[0], warpend[1]+self.style.warp_gap)
        threadingend = self.paint_threading(threadingstart, draw)
        self.paint_tieup_status((warpend[0]+self.style.drawdown_gap, warpstart[1]), draw)
        
        tieupstart = (threadingend[0]+self.style.drawdown_gap, threadingstart[1])
        treadlingstart = (threadingend[0]+self.style.drawdown_gap, threadingend[1]+self.style.drawdown_gap)
        tieupend=(0,0)
        if self.show_liftplan or self.draft.liftplan:
            treadlingend = self.paint_liftplan(treadlingstart, draw)
        else:
            tieupend = self.paint_tieup(tieupstart, draw)
            treadlingend = self.paint_treadling(treadlingstart, draw)
            
        weftstart = (max(treadlingend[0],tieupend[0])+self.style.weft_gap, threadingend[1]+self.style.drawdown_gap)
        weftend = self.paint_weft_colors(weftstart, draw)
        
        drawdownstart = (heddleend[0], threadingend[1]+self.style.drawdown_gap)
        drawdownend = self.paint_drawdown(drawdownstart, draw)
        self.paint_start_indicator(drawdownstart, draw)
        
        notesend = drawdownend
        if self.draft.notes:
            notesend = self.paint_notes((drawdownstart[0],drawdownend[1]), self.draft.collected_notes, draw)
        
        del draw
        im = self.pad_image(im)
        return im

    def paint_tieup_status(self, startpos, draw):
        " indicate rising or falling, from file "
        state = "(Rising shed)"
        if not self.draft.rising_shed: state = "(Falling shed)"
        offsetx,offsety = startpos
        
        vcenter_adj = (self.pixels_per_square/10) -1 + (self.pixels_per_square-self.thread_font_size)/2
        draw.text((offsetx * self.pixels_per_square, offsety * self.pixels_per_square +vcenter_adj),
                       state,
                       font=self.thread_font, fill=BLACK.rgb)
        
    def paint_title(self, startpos, draw, titles):
        """ Add the title from Notes and the filename load from
        """
        offsetx,offsety = startpos
        longest = titles[0]
        for t in titles:
            if len(t) > len(longest): longest = t
        textw, texth = draw.textsize(longest, font=self.title_font)
        lineheight = self.style.title_font_size_factor *1.2 #(for spacing)
        
        endwidth = offsetx + textw/self.style.box_size
        endheight = int(offsety + lineheight * len(titles))+1
        for i,title in enumerate(titles[:-1]):
            draw.text((offsetx, (offsety + i*lineheight) * self.pixels_per_square),
                       title,
                       align='left',
                       font=self.title_font,
                       fill=BLACK.rgb)
        # do last one (filename) smaller
        draw.text((offsetx, (offsety + (len(titles)-1)*lineheight) * self.pixels_per_square),
                       titles[-1],
                       align='left', font=self.tick_font, fill=BLACK.rgb)
        
        return (endwidth, endheight)
        
    def paint_ministats(self, startpos, stats, draw):
        """ Short series of hopefully useful observations """
        offsetx,offsety = startpos
        longest = stats[0]
        for t in stats:
            if len(t) > len(longest): longest = t
        textw, texth = draw.textsize(longest, font=self.tick_font)
        endwidth = offsetx + textw/self.pixels_per_square
        lineheight = self.style.title_font_size_factor *1.02 #(for spacing)
        endheight = int(offsety + lineheight * len(stats))+1
        
        for i,stat in enumerate(stats):
            draw.text((offsetx, (offsety + i*lineheight) * self.pixels_per_square),
                       stat,align='left',
                       font=self.tick_font, fill=BLACK.rgb)
        return (endwidth, endheight)

    def paint_notes(self, startpos, notes, draw):
        """ The Notes from the wif file.
            - Also show creation date and s/w used
        """
        # notes are a list of strings(lines)
        offsetx,offsety = startpos
        longest = ""
        lines = ["Notes:"]
        for note in notes:
            lines.append(note)
            if len(note) > len(longest): longest = note
        textw, texth = draw.textsize(longest, font=self.tick_font)
        endwidth = offsetx + textw/self.pixels_per_square
        lineheight = self.style.title_font_size_factor *1.02 #(for spacing)
        endheight = int(offsety + lineheight * len(lines)) + 1
        
        for i,line in enumerate(lines):
            draw.text((offsetx, (offsety + (i+1)*lineheight) * self.pixels_per_square),
                       line,align='left',
                       font=self.tick_font, fill=BLACK.rgb)
        return (endwidth, endheight)
            
    def paint_start_indicator(self, startpos, draw):
        offsetx,offsety = startpos
        starty = offsety * self.pixels_per_square
        topy = (starty - (self.pixels_per_square / 2))
        
        if self.draft.start_at_lowest_thread:
            # right side
            endx = (offsetx + len(self.draft.warp)) * self.pixels_per_square
            startx = endx - self.pixels_per_square
        else:
            # left side
            startx = offsetx
            endx = startx + self.pixels_per_square
        vertices = [
            (startx, topy),
            (endx, topy),
            (startx + (self.pixels_per_square / 2), starty),
        ]
        draw.polygon(vertices, fill=self.boxfill_color.rgb)
    
    def paint_heddles_stats(self, startpos, draw):
        " show heddles needed per warp shaft "
        offsetx,offsety = startpos # upper left corner position
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            start_warp_y = offsety + self.style.tick_length
        starty = (offsety+1) * self.pixels_per_square
        startx = offsetx * self.pixels_per_square
        
        vcenter_adj = (self.pixels_per_square/10) -1 + (self.pixels_per_square-self.thread_font_size)/2
        total = 0
        for shaft in self.draft.shafts:
            starty += self.pixels_per_square
            count = len([1 for t in self.draft.warp if t.shaft == shaft])
            total += count
            draw.text((startx, starty+vcenter_adj),
                       "%3d"%(count),
                       font=self.thread_font, fill=BLACK.rgb)
        #
        draw.text((startx, starty + 2 + self.pixels_per_square),
                       "%3d"%(total),
                       font=self.thread_font, fill=BLACK.rgb)
        endwidth  = offsetx + int(3 * self.thread_font_size / self.pixels_per_square)
        endheight = offsety + len(self.draft.shafts) + 1
        return (endwidth, endheight)

    def paint_warp_colors(self, startpos, draw):
        """ Paint each thread as an outlined box, filled with thread color
        - counts backwards as thread one is on RHS
        """
        offsetx,offsety = startpos # upper left corner position
        starty = offsety * self.pixels_per_square
        endy = (offsety+1) * self.pixels_per_square
        endx = offsetx * self.pixels_per_square # start here
        previous = endx
        
        index = len(self.draft.warp)-1
        while index != -1:
            thread = self.draft.warp[index]
            if thread.spacing:
                endx += thread.yarn_width
            else:
                endx += self.style.box_size
            startx = previous
            draw.rectangle((startx, starty, endx, endy),
                           outline=self.outline_color.rgb,
                           fill=thread.color.rgb)
            previous = endx
            index -= 1
        #
        endwidth = int(endx/self.pixels_per_square)
        endheight = offsety + 1
        return (endwidth, endheight)

    def paint_fill_marker(self, draw, box, blobcolor, style, label=None, yarncolor=None):
        startx, starty, endx, endy = box
        textcol = BLACK
        margin = 1

        if yarncolor:
            if yarncolor.close(self.style.background) and style=='solid':
                # yarn color is too close to background and so not visible
                # so  if 'solid' override to draw 'blob' style instead
                style = 'blob'
                bgcolor = None
            else:
                draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                                fill=yarncolor.rgb)
            if yarncolor.intensity < 0.5:
                textcol = WHITE
        
        if style == 'blob' and not yarncolor:
            margin = floor((endx-startx)/5)
            draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                            fill=blobcolor.rgb)
        elif style == 'solid' and not yarncolor:
            draw.rectangle((startx + margin, starty + margin, endx - margin, endy - margin),
                            fill=blobcolor.rgb)
        elif style == 'number' or style == 'XO':
            if style == 'number':
                hcenter_adj = len(label) * self.thread_font_size/4
            else: # "XO"
                hcenter_adj = self.thread_font_size/3
            vcenter_adj = (self.style.box_size/10) -1 + (box[3]-box[1]-self.thread_font_size)/2
            draw.text((startx+ (endx-startx)/2-hcenter_adj, starty+vcenter_adj),
                      label,
                      align='center',
                      font=self.thread_font,
                      fill=textcol.rgb)
            

    def paint_threading(self, startpos, draw):
        num_threads = len(self.draft.warp)
        num_shafts = len(self.draft.shafts)
        bgcolor = None
        label = 'O' # default to rising shed
        if not self.draft.rising_shed:
            label = 'X'
        
        # position
        offsetx,offsety = startpos # upper left corner position
        endheight = len(self.draft.shafts) + offsety
        
        start_tick_y = offsety
        tick_length = self.style.tick_length
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            start_warp_y = start_tick_y + tick_length -1
            endheight += tick_length
        else:
            start_warp_y = start_tick_y -1
        
        distance = offsetx * self.pixels_per_square
        previous = distance
        t_index = len(self.draft.warp)-1 # count this down and use where we see ii
        while t_index != -1:
            thread = self.draft.warp[t_index]
            if thread.spacing:
                distance += thread.yarn_width
            else:
                distance += self.style.box_size
            startx = previous
            endx = distance
            
            if self.style.warp_use_thread_color:
                bgcolor = thread.color

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (start_warp_y + (num_shafts - jj)) * self.pixels_per_square
                endy = starty + self.pixels_per_square
                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft == thread.shaft:
                    # draw threading marker
                    if self.style.warp_style == 'number':
                        label = str(jj+1)
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.warp_style, label, bgcolor)

            # horizontal tick, number if it's a multiple of tick_mod and not the first one
            if self.style.warp_tick_active:
                thread_no = t_index + 1
                if ((thread_no != num_threads) and
                    (thread_no != 0) and
                        (thread_no % self.style.tick_mod == 0)):
                    # draw line
                    tstarty = start_tick_y * self.pixels_per_square
                    tendy = ((start_tick_y + tick_length) * self.pixels_per_square) - 1
                    draw.line((startx, tstarty, startx, tendy),
                              fill=self.tick_color)
                    # draw text
                    draw.text((startx + 2, tstarty + 2),
                              str(thread_no),
                              font=self.tick_font,
                              fill=self.tick_color)
            previous = distance
            t_index -= 1
        #
        endwidth = int(distance/self.pixels_per_square)
        return (endwidth, endheight)
        
    def paint_weft_colors(self, startpos, draw):
        """ Paint the Vertical weft color bar
        """
        offsetx,offsety = startpos
        endwidth = offsetx + 1
        if self.style.weft_tick_active:
            endwidth += self.style.tick_length
        startx = offsetx * self.pixels_per_square
        endx = startx + self.pixels_per_square
        
        endy = offsety * self.pixels_per_square # steps down along the weft
        previous = endy
        index = 0
        while index != len(self.draft.weft):
            thread = self.draft.weft[index]
            if thread.spacing:
                endy += thread.yarn_width
            else:
                endy += self.style.box_size
            draw.rectangle((startx, previous, endx, endy),
                           outline=self.outline_color.rgb,
                           fill=thread.color.rgb)
            previous = endy
            index += 1
        #
        endheight = int(endy/self.pixels_per_square)
        return (endwidth, endheight)

    def paint_liftplan(self, startpos, draw):
        num_threads = len(self.draft.weft)
        bgcolor = None
        label = 'O' # default to rising shaft
        if not self.draft.rising_shed:
            label = 'X'
        
        offsetx,offsety = startpos
        endwidth = len(self.draft.shafts) + offsetx
        if self.style.weft_tick_active:
            endwidth += self.style.tick_length
        
        endy = offsety * self.pixels_per_square # steps down along the weft
        previous = endy
        index = 0
        while index != len(self.draft.weft):
            thread = self.draft.weft[index]
            if thread.spacing:
                endy += thread.yarn_width
            else:
                endy += self.style.box_size
            
            for jj, shaft in enumerate(self.draft.shafts):
                startx = (jj + offsetx) * self.pixels_per_square
                endx = startx + self.pixels_per_square
                draw.rectangle((startx, previous, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft in thread.connected_shafts:
                    # draw liftplan marker
                    if self.style.weft_use_thread_color:
                        bgcolor = thread.color
                    if self.style.weft_style == 'number':
                        label = str(jj+1)
                    self.paint_fill_marker(draw, (startx, previous, endx, endy), self.style.boxfill_color, self.style.weft_style, label, bgcolor)

            # vertical tick, number if it's a multiple of tick_mod and not the first one
            if self.style.weft_tick_active:
                thread_no = index+1 #ii + 1
                if ((thread_no != num_threads) and
                    (thread_no != 0) and
                        (thread_no % self.style.tick_mod == 0)):
                    # draw line
                    tick_endx = startx + (self.style.tick_length * self.pixels_per_square)
                    draw.line((endx, endy, tick_endx, endy),
                              fill=self.tick_color)
                    # draw text
                    draw.text((endx + self.tick_font_size/4, endy - 2 - self.tick_font_size),
                              str(thread_no),
                              font=self.tick_font,
                              fill=self.tick_color)
            #
            previous = endy
            index += 1
        #
        endheight = int(endy/self.pixels_per_square)
        return (endwidth, endheight) 

    def paint_tieup(self, startpos, draw):
        offsetx = startpos[0]
        label = 'O' # default to rising shaft
        if not self.draft.rising_shed:
            label = 'X'
        
        start_tick_y = startpos[1]
        tick_length = self.style.tick_length
        end_tick = start_tick_y + tick_length
        start_tieup_y = start_tick_y - 1
        if self.style.warp_tick_active or self.style.tieup_tick_active:
            start_tieup_y += tick_length
        endwidth = len(self.draft.treadles) + offsetx
        endheight = len(self.draft.shafts) + startpos[1]
        
        num_treadles = len(self.draft.treadles)
        num_shafts = len(self.draft.shafts)

        for ii, treadle in enumerate(self.draft.treadles):
            startx = (ii + offsetx) * self.pixels_per_square
            endx = startx + self.pixels_per_square

            treadle_no = ii + 1

            for jj, shaft in enumerate(self.draft.shafts):
                starty = (num_shafts - jj + start_tieup_y) * self.pixels_per_square
                endy = starty + self.pixels_per_square

                draw.rectangle((startx, starty, endx, endy),
                               outline=self.outline_color.rgb)

                if shaft in treadle.shafts:
                    if self.style.tieup_style == 'number':
                        label = str(jj+1)
                    self.paint_fill_marker(draw, (startx, starty, endx, endy), self.style.boxfill_color, self.style.tieup_style, label, None)

                # vertical tick, number if it's a multiple of tick_mod and not the first one
                if self.style.tieup_tick_active:
                    if treadle_no == num_treadles:
                        shaft_no = jj + 1
                        if (shaft_no != 0) and (shaft_no % self.style.tick_mod == 0):
                            # draw line
                            line_startx = endx
                            line_endx = line_startx + (self.style.tick_length * self.pixels_per_square)
                            line_starty = line_endy = starty
                            draw.line((line_startx, line_starty,
                                       line_endx, line_endy),
                                       fill=self.tick_color)
                            draw.text((line_startx + 2, line_starty),
                                       str(shaft_no),
                                       font=self.tick_font,
                                       fill=self.tick_color)
            
            # horizontal ticks, number if it's a multiple of tick_mod and not the first one
            if self.style.tieup_tick_active:
                if (treadle_no != 0) and (treadle_no % self.style.tick_mod == 0):
                    # draw line
                    startx = endx = (treadle_no + offsetx) * self.pixels_per_square
                    starty = start_tick_y * self.pixels_per_square
                    endy = (end_tick * self.pixels_per_square) - 1
                    draw.line((startx, starty, endx, endy),
                              fill=self.tick_color)
                    # draw text on left side, right justified
                    textw, texth = draw.textsize(str(treadle_no), font=self.thread_font)
                    draw.text((startx - textw*1.6, starty + 2),
                              str(treadle_no),
                              font=self.tick_font,
                              fill=self.tick_color)
        #
        return (endwidth, endheight)

    def paint_treadling(self, startpos, draw):
        
        num_threads = len(self.draft.weft)
        bgcolor = None
        label = 'O' # default to rising shed
        if not self.draft.rising_shed:
            label = 'X'
        
        offsetx, offsety = startpos
        endwidth = len(self.draft.treadles) + offsetx
        if self.style.weft_tick_active:
            endwidth += self.style.tick_length
        
        endy = offsety * self.pixels_per_square # steps down along the weft
        previous = endy
        index = 0
        while index != len(self.draft.weft):
            thread = self.draft.weft[index]
            if thread.spacing:
                endy += thread.yarn_width
            else:
                endy += self.style.box_size
            if self.style.weft_use_thread_color:
                bgcolor = thread.color

            for jj, treadle in enumerate(self.draft.treadles):
                startx = (jj + offsetx) * self.pixels_per_square
                endx = startx + self.pixels_per_square
                draw.rectangle((startx, previous, endx, endy),
                               outline=self.outline_color.rgb)

                if treadle in thread.treadles:
                    # draw treadling marker
                    if self.style.weft_style == 'number':
                        label = str(jj+1)
                    self.paint_fill_marker(draw, (startx, previous, endx, endy), self.style.boxfill_color, self.style.weft_style, label, bgcolor)
            # vertical tick, number if it's a multiple of tick_mod and not the first one
            if self.style.weft_tick_active:
                # ii = index
                thread_no = index + 1
                if ((thread_no != num_threads) and
                    (thread_no != 0) and
                        (thread_no % self.style.tick_mod == 0)):
                    # draw line
                    tick_endx = endx + (self.style.tick_length * self.pixels_per_square)
                    draw.line((endx, endy, tick_endx, endy),
                              fill=self.tick_color)
                    # draw text
                    draw.text((endx + self.tick_font_size/4, endy - 2 - self.tick_font_size),
                              str(thread_no),
                              font=self.tick_font,
                              fill=self.tick_color)
            #
            previous = endy
            index += 1
        #
        endheight = int(endy/self.pixels_per_square)
        return (endwidth, endheight)

    def get_position(self, thread, start, end, x_reversed=False):
        """ Iterate over the threads calculating the proper position for any given float
             - assuming spacing defined
        """
        num_warp_threads = len(self.draft.warp)
        # reversed for back of cloth
        begin = num_warp_threads
        step = -1
        if x_reversed:
            step = 1
        
        if thread.spacing:
            # starty (step through the wefts)
            w = 0
            for i in range(start[1]):
                w += self.draft.weft[i].yarn_width
            starty = w
            # endy
            w = 0
            for i in range(end[1]+1):
                w += self.draft.weft[i].yarn_width
            endy = w
            # startx (step through the warps)
            w = 0
            for i in range(num_warp_threads-1, end[0], -1):
                w += self.draft.warp[i].yarn_width
            startx = w
            # endx
            w = 0
            for i in range(num_warp_threads-1, start[0]-1, -1):
                w += self.draft.warp[i].yarn_width
            endx = w

        else: # no spacing info so use pixels_per_square
            startx = (num_warp_threads - end[0]-1) * self.pixels_per_square 
            starty = start[1] * self.pixels_per_square
            endx = (num_warp_threads - start[0]) * self.pixels_per_square
            endy = (end[1] + 1) * self.pixels_per_square
        #
        result_start = (startx, starty)
        result_end   = (endx, endy)
        return (result_start, result_end)

        
    def paint_drawdown(self, startpos, draw):
        num_threads = len(self.draft.warp)
        floats = self.draft.computed_floats
        # drawdown styles = [solid | box | intersect | boxshaded | solidshaded]
        
        float_color = self.style.floats_color
        float_cutoff = self.style.floats_count
        show_float = self.style.show_floats
        
        offsetx,offsety = startpos
        offsetx *= self.pixels_per_square
        offsety *= self.pixels_per_square
        
        for start, end, visible, length, thread in floats:
            if visible:
                realpos = self.get_position(thread, start, end, True)
                (startx,starty), (endx,endy) = realpos
                startx += offsetx
                starty += offsety
                endx += offsetx
                endy += offsety
                
                outline_color = self.outline_color.rgb
                fill_color = thread.color.rgb
                if show_float and length >= float_cutoff:
                    outline_color = WHITE.rgb
                    fill_color = float_color.rgb
                draw.rectangle((startx, starty, endx, endy),
                               outline=outline_color,
                               fill=fill_color)
        #
        endwidth = int(endx/self.pixels_per_square)
        endheight = int(endy/self.pixels_per_square)
        return (endwidth, endheight)

    def show(self):
        """ Used if no outfile defined. Show it
        """
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
        width_squares_estimate = len(self.draft.warp) + 6
        if self.liftplan or self.draft.liftplan:
            width_squares_estimate += len(self.draft.shafts)
        else:
            width_squares_estimate += len(self.draft.treadles)

        height_squares_estimate = len(self.draft.weft) + 6 + len(self.draft.shafts)

        width = width_squares_estimate * self.scale
        height = height_squares_estimate * self.scale

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
        print(SVG.g(id='warp_threads',*grp))
        doc.append(SVG.g(id="warp_threads",*grp))

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
        floats = self.draft.computed_floats

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