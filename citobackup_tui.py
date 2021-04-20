#!/usr/bin/env python3

"""
Text User Interface for cito_backup

WARNING: This is under development, do not use
"""

import os
import traceback
import argparse
import curses
import curses.panel

from citobackup_restic import Restic


# ----- Start of configuration -----

ETCDIR = "/etc/citobackup"

# ----- End of configuration -----

# ----- globals --------------------------------------------------------


# ----------------------------------------------------------------------


class Menu:
    def __init__(self):
        self.s = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.s.keypad(1)

        self.menu()

        curses.nocbreak()
        self.s.keypad(0)
        curses.echo()
        curses.endwin()

    def updown(self, inc):
        new_row = self.current_row + inc
        if new_row < 0 or new_row >= len(backups):
            return

        # remove highlight old row
        self.s.addstr(self.current_row + 2, 2, self.rows[self.current_row])

        # Add highlight new row
        self.current_row = new_row
        self.s.addstr(self.current_row + 2, 2, self.rows[self.current_row], curses.A_BOLD)

    def menu(self):
        self.s.border(0)
        self.s.addstr(1, 1, "Repositories")
        self.current_row = 0

        y = 2
        self.rows = {}
        for hostname, backup in backups.iter():
            self.s.addstr(y, 2, hostname)
            self.rows[y-2] = hostname
            y += 1

        self.updown(0)

        self.s.refresh()
        while True:
            x = self.s.getch()
            if x == ord("q"):
                break
            elif x == curses.KEY_DOWN:
                self.updown(1)
                self.s.refresh()
            elif x == curses.KEY_UP:
                self.updown(-1)
                self.s.refresh()
            elif x == ord("s"):
                self.show_snapshots(self.rows[self.current_row])
                self.s.refresh()
            else:
                self.s.addstr(0, 3, "          ")
                self.s.addstr(0, 3, str(x))
                self.s.refresh()

    def show_snapshots(self, hostname):
        self.pad = curses.newpad(1000, 80)
        self.pad.scrollok(True)
        for y in range(10):
            if y % 2 == 0:
                self.pad.addstr(y, 2, "asd")
                # self.pad.addch(y, 2, "+")
            else:
                self.pad.addch(y, 2, "-")
        self.pad.refresh(0, 0, 0, 20, 20, 20)

        while True:
            curses.doupdate()
            x = self.s.getch()
            if x == ord("q"):
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etcdir",
                        default=ETCDIR,
                        )
    parser.add_argument("-H", "--hostname",
                        )
    parser.add_argument("-p", "--port",
                        default=22,
                        )
    parser.add_argument("--id",
                        )

    args = parser.parse_args()
    
    restic = Restic()

    try:
        menu = Menu()
    except:
        os.system("reset")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
