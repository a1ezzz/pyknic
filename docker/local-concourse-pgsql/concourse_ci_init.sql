
CREATE USER concourse_user;

CREATE DATABASE concourse;

ALTER DATABASE concourse OWNER TO concourse_user;

GRANT ALL PRIVILEGES ON DATABASE concourse TO concourse_user;
