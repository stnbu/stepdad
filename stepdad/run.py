# -*- coding: utf-8 -*-

from main import DumbSetup
from optparse import OptionParser
import sys

def main():
    parser = OptionParser(
            usage="usage: %prog [options] SCRIPT-TO-RUN [SCRIPT-ARGUMENTS]")

    parser.add_option("-o", "--output-dir", dest='root_path', action="store", type="str", default="", help="Put output files in this directory")
    parser.add_option("-g", "--guess", dest='guess', default=True, action="store_true", help="Try to make some guesses about setup() args.")
    parser.add_option("-i", "--interactive", dest='interactive', default=True, action="store_true", help="Interactive. Let the user edit the generaged setup() kwargs.")
    parser.add_option("-p", "--import", dest='import_analysis', default=True, action="store_true", help="Try to analyize the module by importing it.")
    parser.add_option("-s", "--static", dest='static_analysis', default=True, action="store_true", help="Perform some static analysis on the module source.")
    parser.add_option("-j", "--jailed", dest='jailed_exec_analysis', default=True, action="store_true", help="Perform some analysis by loading the module in a \"jailed\" environment.")
    parser.add_option("-t", "--tokenizer", dest='python_tokenizer_analysis', default=True, action="store_true", help="Use the python tonkenizer module to perform some analysis on the module.")
    options, args = parser.parse_args()
    try:
        module_path, = args
    except ValueError:
        ## explain the problem
        parser.print_help()
        sys.exit(1)

    if not options.root_path:
        ## explain the problem
        parser.print_help()
        sys.exit(1)

    ds = DumbSetup(
        module_path=module_path,
        root_path=options.root_path,
        guess=options.guess,
        interactive=options.interactive,
        import_analysis=options.import_analysis,
        static_analysis=options.static_analysis,
        jailed_exec_analysis=options.jailed_exec_analysis,
        python_tokenizer_analysis=options.python_tokenizer_analysis,)
    ds.write_setup_py()
    ds.install_module_to_root_dir()

if __name__=='__main__':
    main()
