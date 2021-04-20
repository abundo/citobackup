#!/usr/bin/env python3

"""
Common stuff for cito_backup
"""

import subprocess
import sys


write_console = sys.stdout.isatty()     # If true, write additonal output

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


def human_readable_size(size):
    """
    """
    index = 0
    tmp = size
    while tmp >= 1000:
        tmp /= 1000
        index += 1
    try:
        return "%0.2f %s" % (tmp, SIZE_UNITS[index])
    except IndexError:
        return size


class Table:
    """
    Class to easily create tables, for CLI or HTML
    """

    class Row:
        def __init__(self):
            self.data = []
            self.column_width = 0

    def __init__(self, headers=None):
        self.rows = []    # list of row[]
        self.row = []     # Current row
        self.column_count = 0  # Number of columns
        self.column_width = []  # Max width of a column

        if headers:
            self.headers = headers
            self.track(headers)
        else:
            self.headers = []

    def track(self, data):
        # data is list of cells

        # adjust number of columns
        if len(data) > self.column_count:
            self.column_count = len(data)

        #
        if self.column_count > len(self.column_width):
            self.column_width += [0] * (self.column_count - len(self.column_width))

        # adjust max width of each column
        for column, cell in enumerate(data):
            if len(cell) > self.column_width[column]:
                self.column_width[column] = len(cell)

    def add_row(self):
        if self.row:
            self.rows.append(self.row)
            self.track(self.row)
            self.row = []   # new row

    def add_cell(self, data):
        self.row.append(str(data))

    def prepare_output(self):
        self.add_row()   # Include last row, if any

        for row in self.rows:
            if len(row) < self.column_count:
                row.append("" * (self.column_count - len(row)))

    def add_line(self, start, middle, end, line):
        r = [start]
        last = self.column_count - 1
        for ix, column_width in enumerate(self.column_width):
            if ix != last:
                r.append("%s%s" % (line * (column_width + 2), middle))
            else:
                r.append("%s%s" % (line * (column_width + 2), end))
        return r

    def __str__(self):
        """
        Return table, suitable to print on console
        """
        self.prepare_output()
        rows = []

        rows.append(self.add_line("\u250c", "\u252c", "\u2510", "\u2500"))
        
        if self.headers:
            r = []
            for column, header in enumerate(self.headers):
                r.append("\u2502%s" % header.ljust(self.column_width[column]+2))
            r.append("\u2502")
            rows.append(r)

            rows.append(self.add_line("\u251c", "\u253c", "\u2524", "\u2500"))

        r = []
        for row in self.rows:
            r = []
            for column, cell in enumerate(row):
                r.append("\u2502 %s " % cell.rjust(self.column_width[column]))
            r.append("\u2502")
            rows.append(r)

        rows.append(self.add_line("\u2514", "\u2534", "\u2518", "\u2500"))

        r = ""
        for row in rows:
            r += "".join(row) + "\n"
        return r

    def as_html(self):
        """
        Return table, html formatted
        """
        self.prepare_output()

        rows = ["<table cellpadding='1' cellspacing='0' border='1'>"]
      
        if self.headers:
            rows.append("<thead>")
            rows.append("  <tr>")
            for column, header in enumerate(self.headers):
                rows.append("    <th align='right'>%s</th>" % header)
            rows.append("  </tr>")
            rows.append("</thead>")

        rows.append("<tbody>")
        for row in self.rows:
            rows.append("  <tr>")
            for column, cell in enumerate(row):
                rows.append("    <td align='right'>%s</td>" % cell)
            rows.append("  </tr>")
        rows.append("</tbody>")

        rows.append("</table>")

        return "\n".join(rows)


class Backup_Result:
    """
    Data from restic json output
    """
    def __init__(self):
        self.errors = []
        self.output = []

        self.hostname = ""
        self.name = ""
        self.subname = ""
        self.backup_type = ""

        self.include_stat = True
        self.files_new = 0
        self.files_changed = 0
        self.files_unmodified = 0
        self.dirs_new = 0
        self.dirs_changed = 0
        self.dirs_unmodified = 0
        self.total_files_processed = 0
        self.total_bytes_processed = 0
        self.total_duration = 0
        self.snapshot_id = 0

    def add_error(self, msg):
        self.errors.append(msg)

    def add_output(self, msg):
        self.output.append(msg)


class Backup_Results:
    """
    Represents status from one hostname backups
    """
    def __init__(self):
        self.results = []

    def add(self, result):
        self.results.append(result)
    
    def __iter__(self):
        for result in self.results:
            yield result


class Backup_Results2:
    """
    Represents status from all backups
    """
    def __init__(self):
        self.backup_results = []

    def add(self, backup_result):
        self.backup_results.append(backup_result)

    def print_summary(self):
        print("<table>")
        print("<th>")
        print("<td>files_new</td>")
        print("<td>files_changed</td>")
        print("<td>files_unmodified</td>")
        print("<td>dirs_new</td>")
        print("<td>dirs_changed</td>")
        print("<td>dirs_unmodified</td>")
        print("<td>total_files_processed</td>")
        print("<td>total_bytes_processed</td>")
        print("<td>total_duration</td>")
        print("<td>snapshot_id</td>")
        print("</th>")

        for backup_result in self.backup_results:
            s = backup_result.backup_stat
            print("<tr>")
            print(f"<td>{s.files_new}</td>")
            print(f"<td>{s.files_changed}</td>")
            print(f"<td>{s.files_unmodified}</td>")
            print(f"<td>{s.dirs_new}</td>")
            print(f"<td>{s.dirs_changed}</td>")
            print(f"<td>{s.dirs_unmodified}</td>")
            print(f"<td>{s.total_files_processed}</td>")
            print(f"<td>{s.total_bytes_processed}</td>")
            print(f"<td>{s.total_duration}</td>")
            print(f"<td>{s.snapshot_id}</td>")
            print("</tr>")

        print("</table>")
    
    def print_details(self):
        pass


def run_cmd(cmd):
    """
    Run a shell command and capture stdout and stderr
    returns (exit_code, stdout/stderr)
    """
    # print("cmd", cmd)
    r = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    txt = r.stdout
    if r.stderr:
        txt += "\n" + r.stderr
    # print("output =", txt.strip())
    # print()
    return r, txt


if __name__ == "__main__":
    # function test
    t = Table(headers=["col1", "col 2", "col A"])
    # t = Table()
    t.add_cell(1)
    t.add_cell(22)
    # t.add_cell(234)
    t.add_row()
    t.add_cell("a")
    t.add_cell("bc")
    t.add_cell("def")
    print(t)
    print(t.as_html())
    sys.exit(1)
