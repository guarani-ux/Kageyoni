-- NEW source-authority optional projection; explicit checked installer only.
-- This DDL is not installed authority or proof of native event authenticity.
CREATE TABLE source_authority(
 branch TEXT NOT NULL,
 id TEXT NOT NULL CHECK(length(id)=81 AND length(CAST(id AS BLOB))=81 AND substr(id,1,17)='source-authority:' AND substr(id,18) NOT GLOB '*[^0-9a-f]*'),
 contract TEXT NOT NULL CHECK(json_valid(contract))
 CHECK(json_type(contract) IS 'object')
 CHECK(json_remove(contract,'$.profile','$.branch','$.workspace_id','$.source_id','$.controller_principal','$.recipient','$.source_payload_hash','$.source_metadata_hash','$.source_pin','$.artifact_pin','$.phase','$.revision')='{}')
 CHECK(json_type(contract,'$.profile') IS 'text' AND json_extract(contract,'$.profile')='samsara-source-authority/20261023-1')
 CHECK(json_type(contract,'$.branch') IS 'text' AND instr(json_extract(contract,'$.branch'),char(0))=0 AND json_extract(contract,'$.branch')=branch)
 CHECK(json_type(contract,'$.workspace_id') IS 'text' AND instr(json_extract(contract,'$.workspace_id'),char(0))=0 AND length(CAST(json_extract(contract,'$.workspace_id') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.source_id') IS 'text' AND instr(json_extract(contract,'$.source_id'),char(0))=0 AND length(CAST(json_extract(contract,'$.source_id') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.controller_principal') IS 'text' AND instr(json_extract(contract,'$.controller_principal'),char(0))=0 AND length(CAST(json_extract(contract,'$.controller_principal') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.recipient') IS 'text' AND instr(json_extract(contract,'$.recipient'),char(0))=0 AND length(CAST(json_extract(contract,'$.recipient') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.source_payload_hash') IS 'text' AND length(json_extract(contract,'$.source_payload_hash'))=64 AND length(CAST(json_extract(contract,'$.source_payload_hash') AS BLOB))=64 AND json_extract(contract,'$.source_payload_hash') NOT GLOB '*[^0-9a-f]*')
 CHECK(json_type(contract,'$.source_metadata_hash') IS 'text' AND length(json_extract(contract,'$.source_metadata_hash'))=64 AND length(CAST(json_extract(contract,'$.source_metadata_hash') AS BLOB))=64 AND json_extract(contract,'$.source_metadata_hash') NOT GLOB '*[^0-9a-f]*')
 CHECK(json_type(contract,'$.source_pin') IS 'object' AND json_remove(json_extract(contract,'$.source_pin'),'$.id','$.version','$.digest')='{}')
 CHECK(json_type(contract,'$.source_pin.id') IS 'text' AND instr(json_extract(contract,'$.source_pin.id'),char(0))=0 AND json_extract(contract,'$.source_pin.id')=json_extract(contract,'$.source_id'))
 CHECK(json_type(contract,'$.source_pin.version') IS 'integer' AND json_extract(contract,'$.source_pin.version')=1)
 CHECK(json_type(contract,'$.source_pin.digest') IS 'text' AND length(json_extract(contract,'$.source_pin.digest'))=64 AND length(CAST(json_extract(contract,'$.source_pin.digest') AS BLOB))=64 AND json_extract(contract,'$.source_pin.digest') NOT GLOB '*[^0-9a-f]*')
 CHECK(json_type(contract,'$.artifact_pin') IS 'object' AND json_remove(json_extract(contract,'$.artifact_pin'),'$.id','$.version','$.digest')='{}')
 CHECK(json_type(contract,'$.artifact_pin.id') IS 'text' AND instr(json_extract(contract,'$.artifact_pin.id'),char(0))=0 AND length(CAST(json_extract(contract,'$.artifact_pin.id') AS BLOB)) BETWEEN 1 AND 512 AND json_extract(contract,'$.artifact_pin.id')<>json_extract(contract,'$.source_id'))
 CHECK(json_type(contract,'$.artifact_pin.version') IS 'integer' AND json_extract(contract,'$.artifact_pin.version')=1)
 CHECK(json_type(contract,'$.artifact_pin.digest') IS 'text' AND json_extract(contract,'$.artifact_pin.digest')=json_extract(contract,'$.source_pin.digest'))
 CHECK(json_type(contract,'$.phase') IS 'text' AND json_extract(contract,'$.phase') IN ('active','withdrawn'))
 CHECK(json_type(contract,'$.revision') IS 'integer' AND ((json_extract(contract,'$.phase')='active' AND json_extract(contract,'$.revision')=1) OR (json_extract(contract,'$.phase')='withdrawn' AND json_extract(contract,'$.revision')=2))),
 PRIMARY KEY(branch,id),
 FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE UNIQUE INDEX source_authority_one_family ON source_authority(branch,json_extract(contract,'$.workspace_id'),json_extract(contract,'$.source_id'));
CREATE TRIGGER source_authority_no_delete BEFORE DELETE ON source_authority BEGIN SELECT RAISE(ABORT,'source authority cannot be deleted'); END;
CREATE TRIGGER source_authority_capture_only BEFORE INSERT ON source_authority
 WHEN json_extract(NEW.contract,'$.phase') IS NOT 'active' OR json_extract(NEW.contract,'$.revision') IS NOT 1
 OR EXISTS(SELECT 1 FROM source_authority WHERE branch=NEW.branch AND (id=NEW.id OR (json_extract(contract,'$.workspace_id')=json_extract(NEW.contract,'$.workspace_id') AND json_extract(contract,'$.source_id')=json_extract(NEW.contract,'$.source_id'))))
 OR NOT EXISTS(SELECT 1 FROM records WHERE branch=NEW.branch AND id=NEW.id AND domain='source_authority' AND version=1 AND status='confirmed' AND visibility='restricted' AND audience_json=json_array(json_extract(NEW.contract,'$.recipient')))
 BEGIN SELECT RAISE(ABORT,'source authority requires new active capture'); END;
CREATE TRIGGER source_authority_withdraw_only BEFORE UPDATE ON source_authority
 WHEN NEW.branch IS NOT OLD.branch OR NEW.id IS NOT OLD.id
 OR json_extract(OLD.contract,'$.phase') IS NOT 'active' OR json_extract(OLD.contract,'$.revision') IS NOT 1
 OR json_extract(NEW.contract,'$.phase') IS NOT 'withdrawn' OR json_extract(NEW.contract,'$.revision') IS NOT 2
 OR json_remove(NEW.contract,'$.phase','$.revision') IS NOT json_remove(OLD.contract,'$.phase','$.revision')
 OR NOT EXISTS(SELECT 1 FROM records WHERE branch=NEW.branch AND id=NEW.id AND domain='source_authority' AND version=2 AND status='confirmed' AND visibility='gm' AND audience_json='[]')
 BEGIN SELECT RAISE(ABORT,'source authority allows only one immutable withdrawal'); END;
CREATE TRIGGER source_authority_record_insert BEFORE INSERT ON records
 WHEN lower(NEW.domain)='source_authority' OR lower(NEW.id) LIKE 'source-authority:%'
 BEGIN
 SELECT CASE WHEN NEW.domain IS NOT 'source_authority' OR substr(NEW.id,1,17) IS NOT 'source-authority:' OR length(NEW.id)<>81 OR length(CAST(NEW.id AS BLOB))<>81 OR substr(NEW.id,18) GLOB '*[^0-9a-f]*' OR NEW.version IS NOT 1 OR NEW.status IS NOT 'confirmed' OR NEW.visibility IS NOT 'restricted' OR json_type(NEW.audience_json) IS NOT 'array' OR json_array_length(NEW.audience_json)<>1 OR json_type(NEW.audience_json,'$[0]') IS NOT 'text' THEN RAISE(ABORT,'invalid source authority capture record') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM records WHERE branch=NEW.branch AND id=NEW.id) THEN RAISE(ABORT,'source authority replacement forbidden') END;
 END;
CREATE TRIGGER source_authority_record_update BEFORE UPDATE ON records
 WHEN lower(OLD.domain)='source_authority' OR lower(NEW.domain)='source_authority' OR lower(OLD.id) LIKE 'source-authority:%' OR lower(NEW.id) LIKE 'source-authority:%'
 BEGIN
 SELECT CASE WHEN OLD.domain IS NOT 'source_authority' OR NEW.domain IS NOT OLD.domain OR NEW.branch IS NOT OLD.branch OR NEW.id IS NOT OLD.id OR OLD.version IS NOT 1 OR NEW.version IS NOT 2 OR OLD.status IS NOT 'confirmed' OR NEW.status IS NOT OLD.status OR OLD.visibility IS NOT 'restricted' OR NEW.visibility IS NOT 'gm' OR NEW.audience_json IS NOT '[]' OR NEW.evidence_json IS NOT OLD.evidence_json OR NEW.updated_event IS OLD.updated_event THEN RAISE(ABORT,'source authority record allows only withdrawal metadata') END;
 END;
CREATE TRIGGER source_authority_record_delete BEFORE DELETE ON records
 WHEN lower(OLD.domain)='source_authority' OR lower(OLD.id) LIKE 'source-authority:%'
 BEGIN SELECT RAISE(ABORT,'source authority record history cannot be deleted'); END;
