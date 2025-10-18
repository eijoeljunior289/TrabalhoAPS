from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import trabalho  # imports functions from the provided trabalho.py (keeps original logic)
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'dev-key'

# Ensure DB initialized (uses trabalho.init_db)
trabalho.init_db()

def row_to_dict(row):
    # sqlite3.Row or tuple
    try:
        return dict(row)
    except Exception:
        # tuple - map by known order used in queries
        return {
            'id': row[0], 'title': row[1], 'description': row[2], 'due': row[3],
            'priority': row[4], 'category': row[5] if len(row) > 5 else None,
            'notify': bool(row[6]) if len(row) > 6 else False
        }

@app.route('/')
def index():
    rows = trabalho.get_tasks(None)
    tasks = []
    for r in rows:
        t = row_to_dict(r)
        # format due for display
        t['due_show'] = trabalho.format_due_iso(t['due'])
        tasks.append(t)
    return render_template('index.html', tasks=tasks)

@app.route('/categories')
def categories():
    cats = trabalho.get_categories()
    categories = [{'id': c[0], 'title': c[1], 'description': c[2]} for c in cats]
    return render_template('categories.html', categories=categories)

@app.route('/new_task', methods=['GET','POST'])
def new_task():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        desc = request.form.get('description','').strip()
        due_raw = request.form.get('due','').strip()
        due_dt = trabalho.parse_datetime_input(due_raw) if due_raw else None
        due_iso = trabalho.iso_or_none(due_dt)
        priority = request.form.get('priority','Baixa')
        cat = request.form.get('category')
        category_id = int(cat) if cat else None
        notify = True if request.form.get('notify') == 'on' else False
        if not title:
            flash('Título obrigatório','error')
            return redirect(url_for('new_task'))
        trabalho.add_task(title, desc, due_iso, priority, category_id, notify)
        return redirect(url_for('index'))
    cats = trabalho.get_categories()
    return render_template('form_task.html', task=None, categories=cats, priorities=trabalho.PRIORITIES)

@app.route('/edit_task/<int:task_id>', methods=['GET','POST'])
def edit_task(task_id):
    row = trabalho.db_execute("SELECT t.id,t.title,t.description,t.due,t.priority,c.title, t.notify, t.notified FROM tasks t LEFT JOIN categories c ON t.category_id = c.id WHERE t.id=?", (task_id,), fetch=True)
    if not row:
        flash('Tarefa não encontrada','error')
        return redirect(url_for('index'))
    existing = row[0]
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        desc = request.form.get('description','').strip()
        due_raw = request.form.get('due','').strip()
        due_dt = trabalho.parse_datetime_input(due_raw) if due_raw else None
        due_iso = trabalho.iso_or_none(due_dt)
        priority = request.form.get('priority','Baixa')
        cat = request.form.get('category')
        category_id = int(cat) if cat else None
        notify = True if request.form.get('notify') == 'on' else False
        trabalho.update_task(task_id, title, desc, due_iso, priority, category_id, notify)
        return redirect(url_for('index'))
    # prepare existing for form
    task = {
        'id': existing[0], 'title': existing[1], 'description': existing[2] or '',
        'due': existing[3] or '', 'priority': existing[4] or 'Baixa',
        'category': existing[5], 'notify': bool(existing[6])
    }
    cats = trabalho.get_categories()
    return render_template('form_task.html', task=task, categories=cats, priorities=trabalho.PRIORITIES)

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    trabalho.delete_task(task_id)
    return redirect(url_for('index'))

@app.route('/new_category', methods=['POST'])
def new_category():
    title = request.form.get('title','').strip()
    desc = request.form.get('description','').strip()
    if title:
        ok = trabalho.add_category(title, desc)
        if not ok:
            flash('Categoria já existe','error')
    return redirect(url_for('categories'))

@app.route('/edit_category/<int:cat_id>', methods=['POST'])
def edit_category(cat_id):
    title = request.form.get('title','').strip()
    desc = request.form.get('description','').strip()
    if title:
        trabalho.update_category(cat_id, title, desc)
    return redirect(url_for('categories'))

@app.route('/delete_category/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
    trabalho.delete_category(cat_id)
    return redirect(url_for('categories'))

# API for notifications - returns tasks due (notified=0, notify=1, due not null and due <= now)
@app.route('/api/notifications')
def api_notifications():
    rows = trabalho.db_execute("""SELECT id,title,due,priority FROM tasks WHERE due IS NOT NULL AND notify=1 AND notified=0""", fetch=True)
    alerts = []
    from datetime import datetime
    now = datetime.now()
    for r in rows:
        tid, title, due_s, priority = r
        try:
            due_dt = datetime.fromisoformat(due_s)
        except Exception:
            continue
        if now >= due_dt:
            alerts.append({'id': tid, 'title': title, 'priority': priority})
            # mark notified so it won't popup again; web client may also call an endpoint to 'open' task later
            trabalho.set_task_notified(tid)
    return jsonify(alerts)

if __name__ == '__main__':
    app.run(debug=True)