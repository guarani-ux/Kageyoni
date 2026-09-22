"""Lossless source archive plus conservative structured extraction.
No generated play is committed to the canonical seed.
"""
import hashlib
from pathlib import Path
import re
from .engine import Engine, require

def _seed(engine, folder):
    require(engine.branch('main')['revision']==0 and not engine.state(),'seed requires empty database')
    files=sorted(Path(folder).glob('*'))
    ledger=next(p for p in files if 'CONTINUITY' in p.name)
    text=ledger.read_text(encoding='utf-8'); sid=ledger.name
    engine.db.execute('BEGIN IMMEDIATE')
    try:
        for p in files:
            if not p.is_file(): continue
            body=p.read_text(encoding='utf-8'); engine.db.execute('INSERT INTO sources VALUES(?,?,?,?)',(p.name,p.name,hashlib.sha256(body.encode('utf-8')).hexdigest(),body))
            lines=body.splitlines(keepends=True); start=0; heading='Preamble'
            for i,line in enumerate(lines):
                if line.startswith('#') and i>start:
                    engine.db.execute('INSERT INTO excerpts VALUES(?,?,?,?,?,?)',(f'{p.name}:{start+1}',p.name,start+1,i,heading,''.join(lines[start:i])))
                    start=i; heading=line.strip()
                elif line.startswith('#'): heading=line.strip()
            if lines: engine.db.execute('INSERT INTO excerpts VALUES(?,?,?,?,?,?)',(f'{p.name}:{start+1}',p.name,start+1,len(lines),heading,''.join(lines[start:])))
    except Exception: engine.db.rollback(); raise
    changes=[]
    def add(domain,id,data,quote,status='confirmed',visibility='gm',audience=None,note='Structured extraction from supplied continuity; not a complete transcript.'):
        require(quote in text, f'quote not in source: {quote}')
        changes.append(dict(op='create',id=id,domain=domain,data=data,status=status,visibility=visibility,audience=audience or [],evidence=[dict(source=sid,quote=quote,note=note)]))
    for id,name,kind,quote in [
        ('gaia','Gaia','island','Gaia is an **island**, not the entire planet.'),
        ('ichimonji','Ichimonji','world','Ichimonji is an actual world substrate'),
        ('booderland','Booderland','world','Alexandra crossed from Booderland'),
        ('external-dark','External Dark','layer','**External Dark:** an uncharted layer'),
        ('deitys-revenge',"The Deity’s Revenge",'ship','Kenway is **not on Gaia**.'),
        ('first-world','First World','layer','a world/history layer from which something was removed'),
        ('threshold','First World threshold','region','The party has not yet entered the deeper layer.')]:
        add('location',id,dict(name=name,kind=kind),quote)
    chars=[
        ('levi','Levi','person','gaia','unknown','Levi (Li Bai)'),
        ('elijah','Elijah','person',None,'partly embedded in the First Revision','He is partly embedded in the First Revision.'),
        ('alexandra','Alexandra','person','threshold','wounded shoulder','**Alexandra:** wounded shoulder'),
        ('xandra-gaia','Xandra of Gaia','person','gaia','exhausted and recovering','Xandra is exhausted and recovering.'),
        ('xandra-ichimonji','Xandra of Ichimonji','person','threshold','archive partially damaged','**Xandra of Ichimonji:** archive partially damaged'),
        ('cloud','Cloud','person','gaia','exhausted but standing','Cloud is exhausted but standing.'),
        ('kenway','Kenway','person','deitys-revenge','unknown','He sailed away aboard The Deity’s Revenge.'),
        ('axiom','Axiom','entity','deitys-revenge','hidden; intention and capabilities unresolved','Axiom secretly tempered/compressed himself'),
        ('maharaga','Maharaga','entity','gaia','sovereign, unresolved force','Maharaga remains a sovereign, unresolved force.'),
        ('time-admiral','Time Admiral','person','gaia','unconscious','The Time Admiral is unconscious.'),
        ('environmental-admiral','Environmental Admiral','person','gaia','exhausted','The Environmental Admiral is exhausted'),
        ('zoro','Shimotsuki Zoro','person','threshold','head wound','**Shimotsuki Zoro:** head wound'),
        ('kurogane','Kurogane Kenpachi','person','threshold','left arm partially numb','**Kurogane Kenpachi:** left arm partially numb'),
        ('ichibei','Ichibei Ichimonji','manifestation','threshold','cannot proceed below threshold','**Ichibei Ichimonji:** manifested'),
        ('mugetsu','Mugetsu','entity',None,'unknown','Mugetsu is the Shadow Sovereign'),
        ('tavian','Tavian','entity',None,'identity-fragment', '**Tavian** is the first identified voice'),
    ]
    known_names={c[1] for c in chars}
    for id,name,kind,location,condition,quote in chars:
        data=dict(name=name,entity_kind=kind,condition=condition,location=location)
        if id=='levi': data['aliases']=['Li Bai','Flowe D. Levi']
        if id=='alexandra': data['aliases']=['Queen Alexandra Booder']
        add('character',id,data,quote)
    # Roster-only references retain unknown identity classifications and present conditions.
    roster=['Imu','Region Nostra','the Prophet','Sebastian Nelson','Queen Edwige Nelson','Hiyori','Garling Figarland','Griffith','Whis','Sciel','Unknown Traveler','Imperium','Zedrof','Yhwach','Father','Madara','Aizen','Orochimaru','Dragon','Sabo','Elowise','Jimbei','Nico Robin','Uta','Makima','Maki Zenin','Kaido','Shanks','Monkey D. Luffy','Boa Hancock','Reze','Killua Zoldyck','Chihiro','Hibari Kyoya','Jupiter','Mars','Warcury','Nusjuro','Benjamin','Shunya','Karma','Dharma','Maya','General Specialist','Antigravity','Total Auditor']
    for name in roster:
        id='roster-'+re.sub('[^a-z0-9]+','-',name.lower()).strip('-')
        add('character',id,dict(name=name,entity_kind='unknown',condition='unknown'),name,note='Name occurs in supplied roster; classification, location and other details require further extraction or evidence.')
    add('faction','oracle',dict(name='Oracle',purpose='Controllable reality',institution='religious empire',leadership='unknown',resources='military, surveillance, propaganda, and command infrastructure'),'The Oracle is a religious empire')
    add('faction','sovereign-crew',dict(name='Sovereign Crew',purpose='Locate what was removed from the First World.',institution='Voluntary crew'),'Alexandra founded a crew based on voluntary alignment')
    for id,name in [('scribe-triad','Scribe Triad'),('world-government','World Government'),('ten-aspects','Ten Aspects'),('legion',"Cloud's Legion of Sovereignty"),('pentarchs','Gorosei/Pale Pentarchs')]:
        add('faction',id,dict(name=name),name,note='Roster group reference; institutional details not supplied.')
    add('world_rule','gaia-balance',dict(name='Gaia balancing law',scope='gaia',statement='No Will may completely suppress another Will inside Gaia.',resolution='gm_judgment',exceptions='Unknown; not moral judgment.'),'No Will may completely suppress another Will inside Gaia.')
    add('environment','mugen',dict(location='gaia',feature='Mugen Furyoku merger',kind='metaphysical',rule='Adaptive environmental physics; not a conscious companion.',duration='persistent; limits unresolved'),'Mugen Furyoku is **not a conscious companion, summon, or speaking entity**.')
    for id,name,function,quote in [
        ('structure','Structure-Structure Fruit','Manipulates relationships and governing arrangements.','Structure-Structure Fruit'),
        ('consequence','Consequence-Consequence Fruit','Coherent intent can force a consequence through temporal reversal.','Her coherent intent can force a consequence through temporal reversal.'),
        ('erosion','Erosion-Erosion Fruit','Soul manifestation involving Erosion.','Erosion-Erosion Fruit'),
        ('sovereign-route','Sovereign Route','Touched boundaries become temporary movement paths.','touched boundaries can become temporary movement paths.'),
        ('status-preservation','Status Preservation','Prevents transformed claims from gaining certainty; cannot establish truth.','compiled **Status Preservation**')]:
        add('ability',id,dict(name=name,function=function,limits='See source; unresolved limits remain unknown.',costs='Not fully established'),quote)
    for char,ability in [('levi','structure'),('xandra-gaia','consequence'),('kenway','erosion'),('alexandra','sovereign-route'),('kurogane','status-preservation')]:
        add('capability',char+'-'+ability,dict(character=char,ability=ability,mastery='limits unresolved',condition='damaged and unstable' if char=='alexandra' else 'established; exact operational limits unresolved'),next(c['evidence'][0]['quote'] for c in changes if c['id']==ability))
    add('will','booder-will',dict(name="Booder's Will",bearer='alexandra',principles='Independent sovereignty',limits='unresolved'),"**Booder's Will** is the correct name")
    for id,name,holder,condition,quote in [
        ('alexandra-blade','Amaterasu Kageyoni no Muchi','alexandra','damaged and unstable','Shikai damaged and unstable'),
        ('zoro-third-sword',"Zoro’s third sword",'zoro','chipped but usable','third sword chipped but usable'),
        ('ichibei-brush',"Ichibei’s brush",'ichibei','broken','broken brush')]:
        add('item',id,dict(name=name,condition=condition),quote)
        add('loadout',id+'-custody',dict(item=id,holder=holder,slot='bonded' if holder=='alexandra' else 'carried',equipped=0),quote,note='Custody linked to the described character; precise equipped slot is not established.')
    add('relationship','cloud-admiral',dict(subject='cloud',object='environmental-admiral',kind='warrior bond',feeling='Mutual recognition and attraction; relationship unresolved.'),'Their conflict developed into mutual recognition and a warrior bond with romantic potential.')
    add('affiliation','admiral-oracle',dict(character='environmental-admiral',faction='oracle',allegiance='estranged',role='Admiral',consent='Current alignment unresolved; not automatically a defector.'),'politically estranged from the Oracle')
    for id in ('alexandra','xandra-ichimonji','zoro'):
        add('affiliation',id+'-crew',dict(character=id,faction='sovereign-crew',allegiance='member',consent='Joined voluntarily'), '### Confirmed members')
    add('political_claim','oracle-control',dict(claimant='oracle',territory='gaia',authority='Attempted suppression/recall of Environmental Admiral',legitimacy='not established',enforcement='Command relationship disrupted',phase='contested'),'The Oracle attempted to suppress or recall her')
    add('arc','first-world-arc',dict(name='First World investigation',phase='active',conflict='Discover the missing relationship; face the rupture.'),'What is the active relationship beneath the First World?')
    add('objective','missing-first-world',dict(title='Locate what was removed from the First World',holder='sovereign-crew',phase='active',success='Established discovery of the missing element',failure='Unresolved'), 'Locate what was removed from the First World.')
    add('scene','threshold-scene',dict(name='First World doorway',location='threshold',phase='active',round=0,context='The party has not entered the deeper layer. Round zero is an engine initialization value, not a recovered combat round. Hazards and positions remain qualitative.',hazards='Something below is writing back; unstable cuts.'),'The party has not yet entered the deeper layer.')
    for char in ('alexandra','xandra-ichimonji','zoro','kurogane','ichibei'):
        add('participation','party-'+char,dict(scene='threshold-scene',character=char,position='At threshold; exact distance unknown'),'### Current party state')
    add('clock','gaia-clock',dict(name='Gaia local elapsed clock',location='gaia',tick=0,unit='unspecified',calendar='unknown',relation_to_others='No numerical conversion established'), 'much less time passed externally.',status='proposed',note='Technical zero origin; not an asserted canon date or elapsed duration.')
    add('experience','xandra-rewinds',dict(character='xandra-gaia',clock='gaia-clock',unit='weeks, approximate',remembered='Retained memory across repeated temporal rewinds; exact duration unknown.',survives_rewind=1),'Subjectively, weeks passed for her and the Time Admiral')
    # Preserve every explicit unresolved question as a separate open thread, without inventing answers.
    heading=''; n=0
    for line in text.splitlines():
        if line.startswith('#'): heading=line
        if ('unresolved' in heading.lower() or 'open questions' in heading.lower()) and re.match(r'^\d+\. ',line):
            n+=1; question=re.sub(r'^\d+\. ','',line)
            add('thread',f'open-question-{n:02}',dict(question=question,phase='answered' if '**Current canon: yes' in question else 'open',answer='Local to Gaia; no automatic planetary reach.' if '**Current canon: yes' in question else None),line)
    sequence_section=text.split('## Major sequence so far\n',1)[1].split('## Current world state',1)[0]
    for line in sequence_section.splitlines():
        if re.match(r'^\d+\. ',line):
            index=line.split('.',1)[0]
            add('historical_account','gaia-history-'+index.zfill(2),dict(assertion=line,event_reference='Gaia ledger sequence '+index,interpretation='Source-recorded sequence; not an engine turn or precise timestamp.'),line)
    add('knowledge','elijah-recognizes',dict(holder='elijah',subject='Alexandra',assertion='Can recognize Alexandra despite severed ordinary bonds.',attitude='knows',basis='Recorded contact'), 'He can recognize her.')
    add('consequence','zoro-cut',dict(subject='zoro-third-sword',effect='Blade connected to deeper First World layer; unstable persistent cuts.',duration='persistent',reversibility='unknown'),'the damaged blade is connected to the deeper First World layer')
    command=dict(api_version=1,branch='main',expected_revision=0,request_id='source-import-v1',kind='import',actor='source-curator',narrative='Conservative structured import of supplied continuity. Full attachments archived. No new story event is being played.',changes=changes)
    receipt = engine.apply(command)
    engine.db.commit()  # Seed owns source import plus event transaction.
    return receipt


def seed(engine, folder):
    try: return _seed(engine, folder)
    except Exception:
        engine.db.rollback()
        raise
