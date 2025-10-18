#!/usr/bin/env python3
"""
Task Manager Prototype
- GUI: Tkinter
- DB: SQLite (file tasks.db)
- Background scheduler: threading (checa notificações)
Implements:
- categories (title, description)
- tasks (title, desc, due datetime, priority, category, notifications on/off)
- edit/delete/move tasks/categories
- notification scheduling in background
"""

import sqlite3
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

DB = "tasks.db"
CHECK_INTERVAL_SECONDS = 30  # checa a cada 30s

PRIORITIES = ["Baixa", "Média", "Alta"]


# ---------- database ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL,
        description TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due TEXT, -- ISO datetime string or NULL
        priority TEXT CHECK(priority IN ('Baixa','Média','Alta')) DEFAULT 'Baixa',
        category_id INTEGER,
        notify INTEGER DEFAULT 1,
        notified INTEGER DEFAULT 0,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    )""")
    conn.commit()
    conn.close()


def db_execute(query, params=(), fetch=False, many=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if many:
        c.executemany(query, params)
    else:
        c.execute(query, params)
    if fetch:
        rows = c.fetchall()
        conn.close()
        return rows
    conn.commit()
    conn.close()


# ---------- models ----------
def add_category(title, description=""):
    try:
        db_execute("INSERT INTO categories(title,description) VALUES(?,?)", (title, description))
        return True
    except sqlite3.IntegrityError:
        return False


def get_categories():
    return db_execute("SELECT id, title, description FROM categories ORDER BY title", fetch=True)


def update_category(cat_id, title, description):
    db_execute("UPDATE categories SET title=?, description=? WHERE id=?", (title, description, cat_id))


def delete_category(cat_id):
    # move tasks to NULL category or delete? We'll set category_id = NULL (user decision)
    db_execute("UPDATE tasks SET category_id = NULL WHERE category_id = ?", (cat_id,))
    db_execute("DELETE FROM categories WHERE id = ?", (cat_id,))


def add_task(title, description, due_iso, priority, category_id, notify=True):
    db_execute(
        "INSERT INTO tasks(title,description,due,priority,category_id,notify,notified) VALUES(?,?,?,?,?,?,0)",
        (title, description, due_iso, priority, category_id, 1 if notify else 0)
    )


def get_tasks(category_id=None):
    if category_id is None:
        return db_execute("""SELECT t.id,t.title,t.description,t.due,t.priority,c.title, t.notify, t.notified
                             FROM tasks t LEFT JOIN categories c ON t.category_id = c.id
                             ORDER BY t.due IS NULL, t.due""", fetch=True)
    else:
        return db_execute("""SELECT t.id,t.title,t.description,t.due,t.priority,c.title, t.notify, t.notified
                             FROM tasks t LEFT JOIN categories c ON t.category_id = c.id
                             WHERE t.category_id = ?
                             ORDER BY t.due IS NULL, t.due""", (category_id,), fetch=True)


def update_task(task_id, title, description, due_iso, priority, category_id, notify):
    db_execute("""UPDATE tasks SET title=?,description=?,due=?,priority=?,category_id=?,notify=?,notified=0 WHERE id=?""",
               (title, description, due_iso, priority, category_id, 1 if notify else 0, task_id))


def delete_task(task_id):
    db_execute("DELETE FROM tasks WHERE id=?", (task_id,))


def set_task_notified(task_id):
    db_execute("UPDATE tasks SET notified=1 WHERE id=?", (task_id,))


# ---------- utilities ----------
def parse_datetime_input(text):
    """Esperado: 'YYYY-MM-DD HH:MM', 'YYYY-MM-DDTHH:MM' (do datetime-local) ou '' para None"""
    text = text.strip()
    if not text:
        return None
    try:
        # Tenta o formato com 'T' (de datetime-local)
        if 'T' in text:
            dt = datetime.strptime(text, "%Y-%m-%dT%H:%M")
        # Tenta o formato com espaço (manual/antigo)
        else:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        return dt
    except ValueError:
        return None


def iso_or_none(dt):
    # Para o banco, ainda usamos o padrão com espaço
    return dt.isoformat(sep=' ') if dt else None


def format_due_iso(s):
    if not s:
        return "Sem data"
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s


# ---------- notification/background ----------
class NotifierThread(threading.Thread):
    daemon = True

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                now = datetime.now()
                rows = db_execute("""SELECT id,title,due,priority,notify,notified FROM tasks WHERE due IS NOT NULL AND notify=1 AND notified=0""",
                                  fetch=True)
                for r in rows:
                    task_id, title, due_s, priority, notify, notified = r
                    try:
                        due_dt = datetime.fromisoformat(due_s)
                    except Exception:
                        continue
                    # se o horário passou ou estiver dentro de 1 minuto -> notificar
                    if now >= due_dt:
                        # aplicar regras por prioridade:
                        # Baixa: popup sem som
                        # Média: popup com som (simulado com bell)
                        # Alta: popup com som e exige ir para app (simulação: botão "Abrir")
                        def _show():
                            self.app.show_notification_popup(task_id, title, priority)
                        # GUI updates from thread -> use app.root.after
                        self.app.root.after(0, _show)
                        set_task_notified(task_id)
                # dorme
            except Exception as e:
                print("Erro no scheduler:", e)
            self.stop_event.wait(CHECK_INTERVAL_SECONDS)

    def stop(self):
        self.stop_event.set()


# ---------- GUI ----------
class TaskManagerApp:
    def __init__(self, root):
        self.root = root
        root.title("Task Manager - Protótipo")
        root.geometry("900x600")
        self.setup_ui()
        self.scheduler = NotifierThread(self)
        self.scheduler.start()
        self.refresh_categories()

    def setup_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: categories
        left = ttk.Frame(main, width=250)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0,8))

        ttk.Label(left, text="Categorias").pack(anchor=tk.W)
        self.cat_list = tk.Listbox(left, height=20)
        self.cat_list.pack(fill=tk.Y, expand=False)
        self.cat_list.bind("<<ListboxSelect>>", lambda e: self.on_category_select())

        cat_btn_frame = ttk.Frame(left)
        cat_btn_frame.pack(fill=tk.X, pady=6)
        ttk.Button(cat_btn_frame, text="Nova", command=self.on_new_category).pack(side=tk.LEFT, padx=2)
        ttk.Button(cat_btn_frame, text="Editar", command=self.on_edit_category).pack(side=tk.LEFT, padx=2)
        ttk.Button(cat_btn_frame, text="Excluir", command=self.on_delete_category).pack(side=tk.LEFT, padx=2)
        ttk.Button(cat_btn_frame, text="Mostrar Todas", command=self.on_show_all).pack(side=tk.LEFT, padx=2)

        # Right: tasks
        right = ttk.Frame(main)
        right.pack(fill=tk.BOTH, expand=True)

        top_controls = ttk.Frame(right)
        top_controls.pack(fill=tk.X)
        ttk.Button(top_controls, text="Nova Tarefa", command=self.on_new_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_controls, text="Editar Tarefa", command=self.on_edit_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_controls, text="Excluir Tarefa", command=self.on_delete_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_controls, text="Mover Tarefa", command=self.on_move_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_controls, text="Atualizar", command=self.refresh_tasks).pack(side=tk.LEFT, padx=4)

        # task tree
        cols = ("Título", "Descrição", "Vencimento", "Prioridade", "Categoria", "Notify")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(8,0))

    def refresh_categories(self):
        cats = get_categories()
        self.cat_list.delete(0, tk.END)
        self.cat_map = {i: cat for i, cat in enumerate(cats)}
        for i, cat in enumerate(cats):
            self.cat_list.insert(tk.END, f"{cat[1]}")  # title

        self.refresh_tasks()

    def get_selected_category(self):
        sel = self.cat_list.curselection()
        if not sel:
            return None
        idx = sel[0]
        return self.cat_map.get(idx)

    def on_category_select(self):
        self.refresh_tasks()

    def on_show_all(self):
        self.cat_list.selection_clear(0, tk.END)
        self.refresh_tasks()

    def on_new_category(self):
        title = simpledialog.askstring("Nova Categoria", "Título da categoria:")
        if not title:
            return
        desc = simpledialog.askstring("Nova Categoria", "Descrição (opcional):") or ""
        ok = add_category(title.strip(), desc)
        if not ok:
            messagebox.showerror("Erro", "Categoria já existe.")
        self.refresh_categories()

    def on_edit_category(self):
        cat = self.get_selected_category()
        if not cat:
            messagebox.showinfo("Info", "Selecione uma categoria.")
            return
        cat_id, title, description = cat
        new_title = simpledialog.askstring("Editar Categoria", "Título:", initialvalue=title)
        if not new_title:
            return
        new_desc = simpledialog.askstring("Editar Categoria", "Descrição:", initialvalue=description) or ""
        update_category(cat_id, new_title.strip(), new_desc)
        self.refresh_categories()

    def on_delete_category(self):
        cat = self.get_selected_category()
        if not cat:
            messagebox.showinfo("Info", "Selecione uma categoria.")
            return
        cat_id, title, _ = cat
        if messagebox.askyesno("Confirmar", f"Excluir categoria '{title}'? As tarefas serão desvinculadas."):
            delete_category(cat_id)
            self.refresh_categories()

    def refresh_tasks(self):
        sel = self.get_selected_category()
        cat_id = sel[0] if sel else None
        rows = get_tasks(cat_id)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            task_id, title, desc, due, priority, cat_title, notify, notified = r
            due_show = format_due_iso(due)
            cat_title = cat_title or "Sem categoria"
            notify_text = "Sim" if notify else "Não"
            self.tree.insert("", tk.END, iid=str(task_id), values=(title, (desc[:40] + '...') if desc and len(desc) > 40 else (desc or ""),
                                                                    due_show, priority, cat_title, notify_text))

    def ask_task_details(self, existing=None):
        # existing: tuple (id,title,desc,due,priority,cat_title,notify,notified)
        title = simpledialog.askstring("Tarefa", "Título:", initialvalue=(existing[1] if existing else ""))
        if not title:
            return None
        desc = simpledialog.askstring("Tarefa", "Descrição (opcional):", initialvalue=(existing[2] if existing else "")) or ""
        due_hint = "YYYY-MM-DD HH:MM (ex: 2025-10-09 14:30) ou vazio"
        due_in = simpledialog.askstring("Tarefa", f"Data e hora de vencimento ({due_hint}):", initialvalue=(existing[3] if existing and existing[3] else ""))
        due_dt = parse_datetime_input(due_in or "")
        if due_in and due_dt is None:
            messagebox.showerror("Erro", "Formato de data/hora inválido. Use 'YYYY-MM-DD HH:MM' ou deixe vazio.")
            return None
        # priority selection
        pr = simpledialog.askstring("Prioridade", f"Prioridade ({'/'.join(PRIORITIES)}):", initialvalue=(existing[4] if existing else "Baixa"))
        if pr not in PRIORITIES:
            messagebox.showinfo("Info", f"Prioridade inválida. Definida como 'Baixa'.")
            pr = "Baixa"
        # category selection
        cats = get_categories()
        cat_map = {str(i+1): cat for i, cat in enumerate(cats)}
        cat_prompt = "Escolha categoria (digite número) ou deixe vazio:\n"
        for k, cat in cat_map.items():
            cat_prompt += f"{k}) {cat[1]}\n"
        chosen = simpledialog.askstring("Categoria", cat_prompt, initialvalue="")
        cat_id = None
        if chosen and chosen.strip() in cat_map:
            cat_id = cat_map[chosen.strip()][0]
        notify_choice = simpledialog.askstring("Notificações", "Ativar notificações? (Sim/Não):", initialvalue=("Sim" if (existing and existing[6]) else "Sim"))
        notify = (notify_choice is None) or notify_choice.lower().startswith("s")
        return {
            "title": title.strip(),
            "desc": desc.strip(),
            "due": iso_or_none(due_dt),
            "priority": pr,
            "category_id": cat_id,
            "notify": notify
        }

    def on_new_task(self):
        details = self.ask_task_details(None)
        if not details:
            return
        add_task(details["title"], details["desc"], details["due"], details["priority"], details["category_id"], details["notify"])
        self.refresh_tasks()

    def get_selected_task_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def on_edit_task(self):
        tid = self.get_selected_task_id()
        if not tid:
            messagebox.showinfo("Info", "Selecione uma tarefa.")
            return
        row = db_execute("SELECT t.id,t.title,t.description,t.due,t.priority,c.title, t.notify, t.notified FROM tasks t LEFT JOIN categories c ON t.category_id = c.id WHERE t.id=?", (tid,), fetch=True)
        if not row:
            messagebox.showerror("Erro", "Tarefa não encontrada.")
            return
        existing = row[0]
        details = self.ask_task_details(existing)
        if not details:
            return
        # find category id if chosen by name
        update_task(tid, details["title"], details["desc"], details["due"], details["priority"], details["category_id"], details["notify"])
        self.refresh_tasks()

    def on_delete_task(self):
        tid = self.get_selected_task_id()
        if not tid:
            messagebox.showinfo("Info", "Selecione uma tarefa.")
            return
        if messagebox.askyesno("Confirmar", "Excluir tarefa?"):
            delete_task(tid)
            self.refresh_tasks()

    def on_move_task(self):
        tid = self.get_selected_task_id()
        if not tid:
            messagebox.showinfo("Info", "Selecione uma tarefa.")
            return
        cats = get_categories()
        options = {str(i+1): cat for i, cat in enumerate(cats)}
        prompt = "Escolha a categoria destino (número) ou vazio para 'Sem categoria':\n"
        for k, cat in options.items():
            prompt += f"{k}) {cat[1]}\n"
        chosen = simpledialog.askstring("Mover", prompt, initialvalue="")
        cat_id = None
        if chosen and chosen.strip() in options:
            cat_id = options[chosen.strip()][0]
        # update only category
        db_execute("UPDATE tasks SET category_id = ? WHERE id = ?", (cat_id, tid))
        self.refresh_tasks()

    def show_notification_popup(self, task_id, title, priority):
        # Simula as regras:
        # Baixa: popup sem som
        # Média: popup com som (root.bell)
        # Alta: popup com som e precisa "Entrar no app" (aqui simulamos oferecendo botão 'Abrir')
        if priority == "Média":
            try:
                self.root.bell()
            except Exception:
                pass
        if priority == "Alta":
            try:
                self.root.bell()
            except Exception:
                pass

        def on_open():
            # abre edição da tarefa
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(1000, lambda: self.root.attributes('-topmost', False))
            # selecionar item na tree
            if str(task_id) in self.tree.get_children():
                self.tree.selection_set(str(task_id))
                self.tree.see(str(task_id))
            popup.destroy()

        popup = tk.Toplevel(self.root)
        popup.title("Alerta de Tarefa")
        ttk.Label(popup, text=f"Tarefa: {title}").pack(padx=12, pady=6)
        ttk.Label(popup, text=f"Prioridade: {priority}").pack(padx=12, pady=6)
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Fechar", command=popup.destroy).pack(side=tk.LEFT, padx=4)
        if priority == "Alta":
            ttk.Button(btn_frame, text="Abrir no app", command=on_open).pack(side=tk.LEFT, padx=4)
        # regras: se Baixa -> sem som (já tratado). Se média -> som (bell). Se alta -> só pode apagar entrando no app (simulado: ao tentar deletar mostramos aviso)
        # popup se mantém por 10s
        popup.after(10000, popup.destroy)

    def on_close(self):
        if messagebox.askokcancel("Sair", "Deseja sair?"):
            self.scheduler.stop()
            self.root.destroy()


def main():
    init_db()
    root = tk.Tk()
    app = TaskManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()