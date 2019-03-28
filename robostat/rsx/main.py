import click
from robostat.rsx.create import create_command
from robostat.rsx.timetable import import_command, export_command
from robostat.rsx.show import show_command
from robostat.rsx.modify import del_command, shadow_command

@click.group()
def main():
    pass

main.add_command(create_command)
main.add_command(import_command)
main.add_command(export_command)
main.add_command(show_command)
main.add_command(del_command)
main.add_command(shadow_command)

if __name__ == "__main__":
    main()
