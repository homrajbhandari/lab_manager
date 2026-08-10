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


def assert_envelope(payload, *, expect_data=True, expect_total=False):
    """Verify the envelope has the expected uniform shape."""
    assert isinstance(payload, dict), f"Expected dict, got {type(payload)}"
    assert set(payload.keys()) >= {"success", "message"}, (
        f"Missing top-level keys, got {list(payload.keys())}"
    )
    if expect_data:
        assert "data" in payload, "Missing 'data' key"
    if expect_total:
        assert "total" in payload, "Missing 'total' key"
    if not payload["success"]:
        assert "error" in payload, "Failed response missing 'error' key"
        assert "code" in payload["error"], "Failed response missing 'error.code'"
    return payload


status, payload = request('GET', '/')
assert_envelope(payload)
print('GET / ->', status, payload['success'], payload['message'])

status, payload = request('GET', '/health')
assert_envelope(payload)
print('GET /health ->', status, payload['data']['status'])

status, project = request('POST', '/projects/', {'title': 'Test Project', 'description': 'Demo', 'status': 'active', 'priority': 'high'})
assert_envelope(project)
project_id = project['data']['id']
print('POST /projects/ ->', status, project['message'], 'id=', project_id)

status, projects = request('GET', '/projects/')
assert_envelope(projects, expect_total=True)
print('GET /projects/ ->', status, 'total=', projects['total'], 'first=', projects['data'][0]['title'])

status, project = request('GET', f'/projects/{project_id}')
assert_envelope(project)
print('GET /projects/{id} ->', status, project['data']['title'])

status, project = request('PUT', f'/projects/{project_id}', {'title': 'Updated Project', 'priority': 'urgent'})
assert_envelope(project)
print('PUT /projects/{id} ->', status, project['data']['title'], project['data']['priority'])

status, task = request('POST', '/tasks/', {'title': 'Test Task', 'description': 'Demo task', 'status': 'pending', 'priority': 'medium', 'project_id': project_id})
assert_envelope(task)
task_id = task['data']['id']
print('POST /tasks/ ->', status, task['message'])

status, task = request('GET', f'/tasks/{task_id}')
assert_envelope(task)
print('GET /tasks/{id} ->', status, task['data']['title'])

status, task = request('PUT', f'/tasks/{task_id}', {'status': 'in_progress'})
assert_envelope(task)
print('PUT /tasks/{id} ->', status, task['data']['status'])

status, invalid_task = request('POST', '/tasks/', {'title': 'Bad', 'project_id': 999999})
assert_envelope(invalid_task, expect_data=False)
assert invalid_task['success'] is False
print('POST /tasks/ invalid project ->', status, invalid_task['error']['code'])

status, inventory = request('POST', '/inventory/', {'name': 'Pipette', 'description': 'Lab item', 'category': 'equipment', 'quantity': 10, 'unit': 'pcs', 'location': 'Shelf A', 'supplier': 'Acme'})
assert_envelope(inventory)
inventory_id = inventory['data']['id']
print('POST /inventory/ ->', status, inventory['message'])

status, inventory = request('GET', f'/inventory/{inventory_id}')
assert_envelope(inventory)
print('GET /inventory/{id} ->', status, inventory['data']['name'])

status, inventory = request('PUT', f'/inventory/{inventory_id}', {'quantity': 5})
assert_envelope(inventory)
print('PUT /inventory/{id} ->', status, inventory['data']['quantity'])

status, invalid_inventory = request('POST', '/inventory/', {'name': 'Bad', 'category': 'equipment', 'quantity': -1, 'unit': 'pcs', 'location': 'Shelf A'})
assert_envelope(invalid_inventory, expect_data=False)
assert invalid_inventory['success'] is False
print('POST /inventory/ invalid quantity ->', status, invalid_inventory['error']['code'])

status, sample = request('POST', '/samples/', {'name': 'Sample A', 'description': 'Test sample', 'sample_type': 'blood', 'status': 'available', 'storage_location': 'Freezer 1', 'project_id': project_id})
assert_envelope(sample)
sample_id = sample['data']['id']
print('POST /samples/ ->', status, sample['message'])

status, sample = request('GET', f'/samples/{sample_id}')
assert_envelope(sample)
print('GET /samples/{id} ->', status, sample['data']['name'])

status, sample = request('PUT', f'/samples/{sample_id}', {'status': 'processed'})
assert_envelope(sample)
print('PUT /samples/{id} ->', status, sample['data']['status'])

status, invalid_sample = request('POST', '/samples/', {'name': 'Bad Sample', 'sample_type': 'blood', 'status': 'available', 'storage_location': 'Freezer 1', 'project_id': 999999})
assert_envelope(invalid_sample, expect_data=False)
assert invalid_sample['success'] is False
print('POST /samples/ invalid project ->', status, invalid_sample['error']['code'])

for path, label in [
    (f'/tasks/{task_id}', 'task'),
    (f'/samples/{sample_id}', 'sample'),
    (f'/inventory/{inventory_id}', 'inventory'),
    (f'/projects/{project_id}', 'project'),
]:
    status, payload = request('DELETE', path)
    assert_envelope(payload)
    print(f'DELETE /{label}s/{{id}} ->', status, payload['message'], 'deleted_id=', payload['data']['id'])

print('\nAll envelope assertions passed.')