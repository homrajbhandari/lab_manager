import json
import urllib.request
import urllib.error

base = 'http://127.0.0.1:8001'


def request(method, path, data=None):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read().decode('utf-8')
            return resp.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode('utf-8')
        return exc.code, json.loads(payload) if payload else None

status, payload = request('GET', '/')
print('GET / ->', status, payload)
status, payload = request('GET', '/health')
print('GET /health ->', status, payload)

status, project = request('POST', '/projects/', {'title': 'Test Project', 'description': 'Demo', 'status': 'active', 'priority': 'high'})
print('POST /projects/ ->', status, project)
project_id = project['id']

status, projects = request('GET', '/projects/')
print('GET /projects/ ->', status, projects[0]['title'] if projects else None)
status, project = request('GET', f'/projects/{project_id}')
print('GET /projects/{id} ->', status, project['title'])
status, project = request('PUT', f'/projects/{project_id}', {'title': 'Updated Project', 'priority': 'urgent'})
print('PUT /projects/{id} ->', status, project['title'], project['priority'])

status, task = request('POST', '/tasks/', {'title': 'Test Task', 'description': 'Demo task', 'status': 'pending', 'priority': 'medium', 'project_id': project_id})
print('POST /tasks/ ->', status, task)
task_id = task['id']
status, task = request('GET', f'/tasks/{task_id}')
print('GET /tasks/{id} ->', status, task['title'])
status, task = request('PUT', f'/tasks/{task_id}', {'status': 'in_progress'})
print('PUT /tasks/{id} ->', status, task['status'])
status, invalid_task = request('POST', '/tasks/', {'title': 'Bad', 'project_id': 999999})
print('POST /tasks/ invalid project ->', status, invalid_task)

status, inventory = request('POST', '/inventory/', {'name': 'Pipette', 'description': 'Lab item', 'category': 'equipment', 'quantity': 10, 'unit': 'pcs', 'location': 'Shelf A', 'supplier': 'Acme'})
print('POST /inventory/ ->', status, inventory)
inventory_id = inventory['id']
status, inventory = request('GET', f'/inventory/{inventory_id}')
print('GET /inventory/{id} ->', status, inventory['name'])
status, inventory = request('PUT', f'/inventory/{inventory_id}', {'quantity': 5})
print('PUT /inventory/{id} ->', status, inventory['quantity'])
status, invalid_inventory = request('POST', '/inventory/', {'name': 'Bad', 'category': 'equipment', 'quantity': -1, 'unit': 'pcs', 'location': 'Shelf A'})
print('POST /inventory/ invalid quantity ->', status, invalid_inventory)

status, sample = request('POST', '/samples/', {'name': 'Sample A', 'description': 'Test sample', 'sample_type': 'blood', 'status': 'available', 'storage_location': 'Freezer 1', 'project_id': project_id})
print('POST /samples/ ->', status, sample)
sample_id = sample['id']
status, sample = request('GET', f'/samples/{sample_id}')
print('GET /samples/{id} ->', status, sample['name'])
status, sample = request('PUT', f'/samples/{sample_id}', {'status': 'processed'})
print('PUT /samples/{id} ->', status, sample['status'])
status, invalid_sample = request('POST', '/samples/', {'name': 'Bad Sample', 'sample_type': 'blood', 'status': 'available', 'storage_location': 'Freezer 1', 'project_id': 999999})
print('POST /samples/ invalid project ->', status, invalid_sample)

status, payload = request('DELETE', f'/tasks/{task_id}')
print('DELETE /tasks/{id} ->', status, payload)
status, payload = request('DELETE', f'/samples/{sample_id}')
print('DELETE /samples/{id} ->', status, payload)
status, payload = request('DELETE', f'/inventory/{inventory_id}')
print('DELETE /inventory/{id} ->', status, payload)
status, payload = request('DELETE', f'/projects/{project_id}')
print('DELETE /projects/{id} ->', status, payload)
