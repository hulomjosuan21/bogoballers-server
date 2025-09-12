# BogoBallers

## 🔹 Overview
A centralised platform to manage basketball leagues & enhance player participation in **Bogo City**. This system aims to make all the processes of barangay and city-wide basketball leagues easier, improve the data process, and provide a better experience for **players**, **league administrators**, **coaches**, **basketball teams**, and **spectators**.

**BogoBallers: Basketball League Management System** aims to improve and assist league administrators, team managers, players, and spectators through the use of digital tools like a web system and application.

## 🔹 Technology Stack

- **Backend:** Python with Quart and SocketIO  
- **Database:** PostgreSQL  
- **Caching:** Redis
- **Rate Limiting:** Limiter
- **Background Tasks:** APScheduler  
- **Frontend Web:** Vite, React, TypeScript
- **Frontend Mobile:** Flutter, Dart 
- **Containerization:** Docker + Docker Compose

## 🔹 Features
- Manage leagues, teams, and player registrations  
- Real-time score updates and notifications  
- Scheduling and match management  
- Role-based access for administrators, managers, and players  
- Live statistics and analytics  

## 🔹 Getting Started

### Prerequisites
- Docker & Docker Compose installed  
- PostgreSQL and Redis services  

### Running the Project
```bash
hypercorn src.server:app --bind 0.0.0.0:5000 --workers 4 --log-level info
```
```bash
npm start
```
