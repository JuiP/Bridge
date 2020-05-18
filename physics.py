#!/usr/bin/python3
"""
This file is part of the 'Physics' Project
Physics is a 2D Physics Playground for Kids (supporting Box2D2)
Physics Copyright (C) 2008, Alex Levenson, Brian Jordan
Elements Copyright (C) 2008, The Elements Team, <elements@linuxuser.at>

Wiki:   http://wiki.laptop.org/wiki/Physics
IRC:    #olpc-physics on irc.freenode.org

Code:   http://dev.laptop.org/git?p=activities/physics
        git clone git://dev.laptop.org/activities/physics

License:  GPLv3 http://gplv3.fsf.org/
"""
import os
from gettext import gettext as _
import logging

from gi.repository import Gtk
from gi.repository import Gdk

import pygame
from pygame.locals import MOUSEBUTTONUP

import Box2D as box2d
from lib.myelements import elements

import tools
from bridge import Bridge


class PhysicsGame:
    def __init__(self, activity=None):
        self.activity = activity
        # Get everything set up
        self.clock = pygame.time.Clock()
        self.in_focus = True
        # Create the name --> instance map for components
        self.toolList = {}
        for c in tools.allTools:
            self.toolList[c.name] = c(self)
        self.currentTool = self.toolList[tools.allTools[0].name]
        # Set up the world (instance of Elements)
        self.box2d = box2d
        self.opening_queue = None
        self.running = True
        self.initialise = True

        self.full_pos_list = []
        self.tracked_bodies = 0

        self.trackinfo = {}

        self.box2d_fps = 50

    def set_game_fps(self, fps):
        self.box2d_fps = fps

    def switch_off_fake_pygame_cursor_cb(self, panel, event):
        self.show_fake_cursor = False

    def switch_on_fake_pygame_cursor_cb(self, panel, event):
        self.show_fake_cursor = True

    def write_file(self, path):
        # Saving to journal
        logging.debug("write_file called")
        additional_data = {
            'trackinfo': self.trackinfo,
            'full_pos_list': self.full_pos_list,
            'tracked_bodies': self.tracked_bodies,
            'cost': self.bridge.cost
        }
        self.world.json_save(path, additional_data)

    def read_file(self, path):
        # Loading from journal
        logging.debug("read_file called")
        self.opening_queue = path

    def run(self):
        if self.initialise:
            self.initialise = False

            # Fake a Sugar cursor for the pyGame canvas area
            self.show_fake_cursor = True
            pygame.mouse.set_cursor((8, 8), (0, 0), (0, 0, 0, 0, 0, 0, 0, 0),
                                    (0, 0, 0, 0, 0, 0, 0, 0))

            cursor_path = os.path.join(os.path.dirname(__file__), 'standardcursor.png')
            logging.error(cursor_path + "CURS")
            self.cursor_picture = pygame.image.load(cursor_path)
            self.cursor_picture.convert_alpha()
            self.canvas.connect('enter_notify_event',
                                self.switch_on_fake_pygame_cursor_cb)
            self.canvas.connect('leave_notify_event',
                                self.switch_off_fake_pygame_cursor_cb)
            self.canvas.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK |
                                   Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.screen = pygame.display.get_surface()
        pygame.font.init()
        self.font = pygame.font.Font(None, 42)  # font object

        # set up the world (instance of Elements)
        self.world = elements.Elements(self.screen.get_size())
        self.world.renderer.set_surface(self.screen)

        self.joystickobject = None
        self.debug = os.getenv("DEBUG_BRIDGE_SUGAR", False)
        # FIXME, change to false

        # create the name --> instance map for components
        self.toolList = {}
        for c in tools.allTools:
            self.toolList[c.name] = c(self)
        self.currentTool = self.toolList[tools.allTools[0].name]

        # set up static environment
        self.world.run_physics = False

        # provided there is a file to call from
        # We need to place each element in the json
        # to their correct position before generating
        # The ground
        if self.opening_queue:
            path = self.opening_queue.encode('ascii', 'convert')
            if os.path.exists(path):
                self.world.json_load(path, serialized=True)
                if 'full_pos_list' in self.world.additional_vars:
                    self.full_pos_list = \
                        self.world.additional_vars['full_pos_list']
                if 'trackinfo' in self.world.additional_vars:
                    self.trackinfo = self.world.additional_vars['trackinfo']
                if 'tracked_bodies' in self.world.additional_vars:
                    self.tracked_bodies = \
                        self.world.additional_vars['tracked_bodies']


        self.bridge = Bridge(self)
        self.bridge.create_world()

        self.running = True
        t = pygame.time.get_ticks()

        if self.opening_queue:
            path = self.opening_queue.encode('ascii', 'convert')
            if os.path.exists(path):
               self.world.json_load(path)
               self.bridge.cost = self.world.additional_vars.get('cost', 0)
               #if 'full_pos_list' in self.world.additional_vars:
                   #self.full_pos_list = \
                       #self.world.additional_vars['full_pos_list']
               #if 'trackinfo' in self.world.additional_vars:
                   #self.trackinfo = self.world.additional_vars['trackinfo']
               #if 'tracked_bodies' in self.world.additional_vars:
                   #self.tracked_bodies = \
                       #self.world.additional_vars['tracked_bodies']

        while self.running:
            if (pygame.time.get_ticks() - t) > 1500:
                t = pygame.time.get_ticks()

            while Gtk.events_pending():
                Gtk.main_iteration()
            if not self.running:
                break

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode(event.size, pygame.RESIZABLE)

                self.currentTool.handleEvents(event, self.bridge)
                # Show the mouse again on mouse up
                if event.type == MOUSEBUTTONUP:
                    # if event.button == 1:
                    self.show_fake_cursor = True

            # Clear Display
            self.screen.fill((80, 160, 240))  # 255 for white

            # Update & Draw World
            self.world.update()
            self.world.draw()
            if self.world.run_physics:
                self.bridge.for_each_frame()
                bodies_present = len(self.world.world.bodies)

                for key, info in self.trackinfo.items():
                    # [host_body, tracker, color, destroyed?]
                    body = info[1]
                    if info[3] is False: # Not destroyed
                        trackdex = info[4]

                        def to_screen(pos):
                            px = self.world.meter_to_screen(
                                pos[0])
                            py = self.world.meter_to_screen(
                                pos[1])
                            py = self.world.renderer.get_surface() \
                                .get_height() - py
                            return (px, py)

                        x = body.position.x
                        y = body.position.y
                        tupled_pos = to_screen((x,y))
                        posx = tupled_pos[0]
                        posy = tupled_pos[1]
                        try:
                            self.full_pos_list[trackdex].append(posx)
                            self.full_pos_list[trackdex].append(posy)
                        except IndexError:
                            self.full_pos_list.append([posx, posy])     


            # draw output from tools
            self.currentTool.draw()

            # Print all the text on the screen
            text = self.font.render(_("Total Cost: %d") %
                                    self.bridge.cost, True, (0, 0, 0))
            textpos = text.get_rect(left=12, top=12)
            self.screen.blit(text, textpos)
            ratio = self.bridge.stress * 100 / self.bridge.capacity
            text = self.font.render(_("Stress: %d%%") % ratio, True, (0, 0, 0))
            textpos = text.get_rect(left=12, top=53)
            self.screen.blit(text, textpos)

            if self.bridge.train_off_screen:
                text = self.font.render(
                    _("Train fell off the screen, press R to try again!"),
                    True, (0, 0, 0))
            elif self.bridge.level_completed:
                text = self.font.render(
                    _("Level completed, well done!!"),
                    True, (0, 0, 0))
                if self.bridge.train_exit:
                    text = self.font.render(
                        _("Press T to send another train."),
                        True, (0, 0, 0))
            else:
                text = self.font.render(
                    _("Press the Spacebar to start/pause."),
                    True, (0, 0, 0))
            textpos = text.get_rect(left=12, top=94)
            self.screen.blit(text, textpos)

            # Show Sugar like cursor for UI consistancy
            if self.show_fake_cursor:
                self.screen.blit(self.cursor_picture,
                                    pygame.mouse.get_pos())

            # Flip Display
            pygame.display.flip()

            # Try to stay at 30 FPS
            self.clock.tick(30)  # originally 50

    def setTool(self, tool):
        self.currentTool.cancel()
        self.currentTool = self.toolList[tool]


def main():
    toolbarheight = 75
    tabheight = 45
    pygame.init()
    pygame.display.init()
    x, y = pygame.display.list_modes()[0]
    screen = pygame.display.set_mode((x, y - toolbarheight - tabheight))
    # create an instance of the game
    game = PhysicsGame(screen)
    # start the main loop
    game.run()


# make sure that main get's called
if __name__ == '__main__':
    main()
