"""Nonmodal analysis windows and recovery menu for the desktop application."""

__release__ = '134'
import tkinter as tk

def restore(window):
    try:
        window.grab_release()
        window.deiconify();window.lift();window.focus_set()
    except tk.TclError:pass

def analysis_window(window):
    # A long-running analysis must not hold an application-wide input grab.
    try:window.grab_release();window.transient('')
    except tk.TclError:pass
    restore(window)

def install_windows_menu(root):
    menu=tk.Menu(root);windows=tk.Menu(menu,tearoff=False)
    def collect(widget):
        found=[]
        for child in widget.winfo_children():
            if isinstance(child,tk.Toplevel):found.append(child)
            found.extend(collect(child))
        return found
    def populate():
        windows.delete(0,'end')
        windows.add_command(label='Restore main window',command=lambda:restore(root))
        windows.add_command(label='Restore all windows',command=lambda:[restore(w) for w in [root]+collect(root)])
        windows.add_separator()
        for w in collect(root):windows.add_command(label=w.title() or str(w),command=lambda win=w:restore(win))
    windows.configure(postcommand=populate);menu.add_cascade(label='Windows',menu=windows);root.configure(menu=menu)
    def evidence():
        from pathlib import Path
        win=tk.Toplevel(root);win.title('Method and parameter evidence — V134');win.geometry('1000x750')
        text=tk.Text(win,wrap='word');text.pack(fill='both',expand=True)
        text.insert('end',(Path(__file__).parent/'DECISIONS_AND_SOURCES_V134.md').read_text(encoding='utf-8'));text.configure(state='disabled')
    menu.add_command(label='Method and parameter sources',command=evidence)
    def coverage():
        from pathlib import Path
        win=tk.Toplevel(root);win.title('Requested feature coverage — V134');win.geometry('1100x780')
        text=tk.Text(win,wrap='word');text.pack(fill='both',expand=True)
        text.insert('end',(Path(__file__).parent/'REQUEST_COVERAGE_V134.md').read_text(encoding='utf-8-sig'));text.configure(state='disabled')
    menu.add_command(label='Requested feature coverage',command=coverage)
    root.bind_all('<Control-Shift-R>',lambda event:[restore(w) for w in [root]+collect(root)],add='+')
