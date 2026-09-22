-- PROPOSED additive DDL only. Not an installed migration. Requires model/validator/workflow integration.
PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE will_definition(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "classification" TEXT NOT NULL CHECK("classification" IN ('primordial','derivative','independent','false','unknown')),
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE will_expression(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "definition" TEXT NOT NULL,
  "bearer" TEXT NOT NULL,
  "legacy_will" TEXT,
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"definition") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"bearer") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"legacy_will") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE will_technique(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "expression" TEXT NOT NULL,
  "ability" TEXT,
  "name" TEXT NOT NULL,
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"ability") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE will_awakening(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "expression" TEXT NOT NULL,
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE will_development(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "expression" TEXT NOT NULL,
  "progression" TEXT,
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"progression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE will_effect(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  "expression" TEXT NOT NULL,
  "technique" TEXT NOT NULL,
  "contract" TEXT NOT NULL CHECK(json_valid("contract")),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,"technique") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
COMMIT;
