-- PROPOSED optional inquiry derivation projection. Not installed by import.
-- Complete Python contract/history verification and checked installer required.
CREATE TABLE source_derivation(
 branch TEXT NOT NULL,
 id TEXT NOT NULL CHECK(length(id)=82 AND length(CAST(id AS BLOB))=82 AND substr(id,1,18)='source-derivation:' AND substr(id,19) NOT GLOB '*[^0-9a-f]*'),
 contract TEXT NOT NULL CHECK(json_valid(contract))
 CHECK(json_type(contract) IS 'object')
 CHECK(json_remove(contract,'$.profile','$.producer','$.branch','$.workspace_id','$.controller_principal','$.recipient','$.request_id','$.payload','$.bindings','$.result_digest','$.result_routes','$.output','$.revision')='{}')
 CHECK(json_type(contract,'$.profile') IS 'text' AND json_extract(contract,'$.profile')='samsara-source-derivation/20261024-1')
 CHECK(json_type(contract,'$.producer') IS 'object' AND json_extract(contract,'$.producer.name') IS 'Documents.inquire' AND json_extract(contract,'$.producer.version') IS '1')
 CHECK(json_type(contract,'$.branch') IS 'text' AND instr(json_extract(contract,'$.branch'),char(0))=0 AND json_extract(contract,'$.branch')=branch)
 CHECK(json_type(contract,'$.workspace_id') IS 'text' AND instr(json_extract(contract,'$.workspace_id'),char(0))=0 AND length(CAST(json_extract(contract,'$.workspace_id') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.controller_principal') IS 'text' AND instr(json_extract(contract,'$.controller_principal'),char(0))=0 AND length(CAST(json_extract(contract,'$.controller_principal') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.recipient') IS 'text' AND instr(json_extract(contract,'$.recipient'),char(0))=0 AND length(CAST(json_extract(contract,'$.recipient') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.request_id') IS 'text' AND instr(json_extract(contract,'$.request_id'),char(0))=0 AND length(CAST(json_extract(contract,'$.request_id') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.payload') IS 'object' AND json_type(contract,'$.bindings') IS 'object' AND json_type(contract,'$.bindings.inputs') IS 'array')
 CHECK(json_type(contract,'$.result_digest') IS 'text' AND length(json_extract(contract,'$.result_digest'))=64 AND length(CAST(json_extract(contract,'$.result_digest') AS BLOB))=64 AND json_extract(contract,'$.result_digest') NOT GLOB '*[^0-9a-f]*')
 CHECK(json_type(contract,'$.result_routes') IS 'array' AND json_array_length(contract,'$.result_routes')=json_array_length(contract,'$.bindings.inputs'))
 CHECK(json_type(contract,'$.output') IS 'object' AND json_type(contract,'$.output.workspace_id') IS 'text' AND json_type(contract,'$.output.viewer') IS 'text' AND json_extract(contract,'$.output.workspace_id')=json_extract(contract,'$.workspace_id') AND json_extract(contract,'$.output.viewer')=json_extract(contract,'$.recipient'))
 CHECK(json_type(contract,'$.output.artifact_id') IS 'text' AND instr(json_extract(contract,'$.output.artifact_id'),char(0))=0 AND length(CAST(json_extract(contract,'$.output.artifact_id') AS BLOB)) BETWEEN 1 AND 512)
 CHECK(json_type(contract,'$.output.digest') IS 'text' AND json_extract(contract,'$.output.digest')=json_extract(contract,'$.result_digest'))
 CHECK(json_type(contract,'$.output.media_type') IS 'text' AND json_extract(contract,'$.output.media_type')='application/json; charset=utf-8')
 CHECK(json_type(contract,'$.output.size') IS 'integer' AND json_extract(contract,'$.output.size') BETWEEN 1 AND 10000000)
 CHECK(json_type(contract,'$.revision') IS 'integer' AND json_extract(contract,'$.revision')=1),
 PRIMARY KEY(branch,id),
 FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE UNIQUE INDEX source_derivation_one_output ON source_derivation(json_extract(contract,'$.output.artifact_id'));
CREATE UNIQUE INDEX source_derivation_one_request ON source_derivation(branch,json_extract(contract,'$.workspace_id'),json_extract(contract,'$.controller_principal'),json_extract(contract,'$.request_id'));
CREATE TRIGGER source_derivation_creation_only BEFORE INSERT ON source_derivation
 WHEN NOT EXISTS(SELECT 1 FROM records WHERE branch=NEW.branch AND id=NEW.id AND domain='source_derivation' AND version=1 AND status='confirmed' AND visibility='restricted' AND audience_json=json_array(json_extract(NEW.contract,'$.recipient')))
 BEGIN SELECT RAISE(ABORT,'derivation requires matching new native record'); END;
CREATE TRIGGER source_derivation_no_update BEFORE UPDATE ON source_derivation BEGIN SELECT RAISE(ABORT,'derivation creation is immutable'); END;
CREATE TRIGGER source_derivation_no_delete BEFORE DELETE ON source_derivation BEGIN SELECT RAISE(ABORT,'derivation creation cannot be deleted'); END;
CREATE TRIGGER source_derivation_record_insert BEFORE INSERT ON records
 WHEN lower(NEW.domain) LIKE 'source_derivation%' OR lower(NEW.id) LIKE 'source-derivation:%'
 BEGIN
 SELECT CASE WHEN NEW.domain IS NOT 'source_derivation' OR substr(NEW.id,1,18) IS NOT 'source-derivation:' OR length(NEW.id)<>82 OR length(CAST(NEW.id AS BLOB))<>82 OR substr(NEW.id,19) GLOB '*[^0-9a-f]*' OR NEW.version IS NOT 1 OR NEW.status IS NOT 'confirmed' OR NEW.visibility IS NOT 'restricted' OR json_type(NEW.audience_json) IS NOT 'array' OR json_array_length(NEW.audience_json)<>1 OR json_type(NEW.audience_json,'$[0]') IS NOT 'text' THEN RAISE(ABORT,'invalid derivation creation wrapper') END;
 END;
CREATE TRIGGER source_derivation_record_update BEFORE UPDATE ON records
 WHEN lower(OLD.domain) LIKE 'source_derivation%' OR lower(NEW.domain) LIKE 'source_derivation%' OR lower(OLD.id) LIKE 'source-derivation:%' OR lower(NEW.id) LIKE 'source-derivation:%'
 BEGIN SELECT RAISE(ABORT,'derivation record is immutable'); END;
CREATE TRIGGER source_derivation_record_delete BEFORE DELETE ON records
 WHEN lower(OLD.domain) LIKE 'source_derivation%' OR lower(OLD.id) LIKE 'source-derivation:%'
 BEGIN SELECT RAISE(ABORT,'derivation record cannot be deleted'); END;
