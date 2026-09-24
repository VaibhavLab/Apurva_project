-- Optional MySQL 8 schema. Tables are also created automatically by Flask.
CREATE DATABASE IF NOT EXISTS mental_health_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mental_health_chatbot;

CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	full_name VARCHAR(100) NOT NULL, 
	username VARCHAR(40) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS conversations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	conversation_id INTEGER NOT NULL, 
	sender VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	sentiment VARCHAR(10) NOT NULL, 
	sentiment_score FLOAT NOT NULL, 
	risk_level VARCHAR(10) NOT NULL, 
	topic VARCHAR(30) NOT NULL, 
	recommendations JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT valid_sender CHECK (sender IN ('user', 'bot')), 
	CONSTRAINT valid_sentiment CHECK (sentiment IN ('positive', 'negative', 'neutral')), 
	CONSTRAINT valid_risk CHECK (risk_level IN ('normal', 'high')), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_conversations_user_id ON conversations (user_id);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);
