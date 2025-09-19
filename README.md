# SecretBox - NFL Analytics & Prediction Platform

A comprehensive Django web application for NFL data analysis, player statistics tracking, and predictive modeling for the 2025 NFL season.

## 🏈 Overview

SecretBox is a sophisticated NFL analytics platform that provides:
- Real-time NFL game schedules and results
- Detailed player and team statistics
- Machine learning-powered predictions for player props and game outcomes
- Interactive web interface for exploring data and predictions
- Caching system for efficient data management

## ✨ Features

### Core Functionality
- **Game Tracking**: View NFL games by week with detailed matchups
- **Player Analytics**: Comprehensive player statistics including passing, rushing, and receiving stats
- **Team Statistics**: Offensive and defensive team performance metrics
- **Predictive Modeling**: ML-powered predictions for player props and game outcomes
- **User Authentication**: Secure login/signup system
- **Data Caching**: Efficient caching system using Parquet files

### Data Sources
- **nflreadpy**: Primary data source for NFL statistics and play-by-play data
- **Real-time Updates**: Automatic data refresh capabilities
- **Historical Data**: Support for 2025 NFL season data

## 🏗️ Architecture

### Backend (Django)
- **Models**: Comprehensive data models for teams, players, games, and statistics
- **Controllers**: Clean separation of business logic in controller modules
- **Services**: NFL data integration and caching services
- **Management Commands**: Data seeding and refresh utilities

### Frontend
- **Templates**: Django templating with modern HTML/CSS
- **Responsive Design**: Mobile-friendly interface
- **Interactive Elements**: Dynamic week selection and game navigation

### Data Layer
- **SQLite Database**: Local development database
- **Parquet Caching**: Efficient data storage and retrieval
- **Pandas/Polars**: Data processing and manipulation

## 📊 Data Models

### Core Entities
- **Team**: NFL team information with colors and metadata
- **Player**: Player details including position, team, and physical attributes
- **Game**: Game schedules, scores, and completion status
- **PlayerStats**: Weekly player performance statistics
- **TeamStats**: Weekly team performance metrics
- **Prediction**: ML model predictions for player props
- **GamePrediction**: Game outcome predictions
- **CachedData**: Data caching for API efficiency

### Statistics Tracked
- **Passing**: Attempts, completions, yards, TDs, interceptions, rating
- **Rushing**: Attempts, yards, TDs
- **Receiving**: Targets, receptions, yards, TDs
- **Advanced**: Air yards, YAC, target share, snap share
- **Team**: Offensive/defensive metrics, EPA, success rate

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd secretbox
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

4. **Create demo data**
   ```bash
   python manage.py seed_demo
   ```

5. **Start the development server**
   ```bash
   python manage.py runserver
   ```

6. **Access the application**
   - Open your browser to `http://127.0.0.1:8000/`
   - Login with demo credentials: `demo` / `demo123`

### Management Commands

- **Seed Demo Data**: `python manage.py seed_demo`
- **Refresh Week Data**: `python manage.py refresh_week --week <week_number>`

## 🎯 Key Features in Detail

### Week View
- Browse games by week (1-18)
- View game matchups with team information
- Access starting quarterback statistics
- Previous week performance data

### Game Detail
- Individual game information
- Team matchup details
- Game timing and status

### Data Caching
- Automatic caching of NFL data to Parquet files
- Efficient data retrieval and storage
- Configurable cache refresh options

### Predictive Analytics
- Machine learning models for player prop predictions
- Game outcome probability calculations
- Confidence intervals and edge calculations

## 🛠️ Technical Stack

### Backend
- **Django 5.0.8**: Web framework
- **SQLite**: Database
- **Pandas 2.2.2**: Data manipulation
- **Polars 1.0.0**: High-performance data processing
- **nflreadpy 0.1.0**: NFL data API

### Data Science
- **NumPy 1.26.4**: Numerical computing
- **Scikit-learn 1.4.2**: Machine learning
- **Joblib 1.4.2**: Model persistence

### Frontend
- **Django Templates**: Server-side rendering
- **Tailwind CSS**: Styling (referenced in templates)
- **Responsive Design**: Mobile-first approach

## 📁 Project Structure

```
secretbox/
├── core/                    # Main Django app
│   ├── controllers/         # Business logic controllers
│   │   ├── auth.py         # Authentication logic
│   │   └── pages.py        # Page controllers
│   ├── management/         # Django management commands
│   │   └── commands/       # Custom commands
│   ├── templates/          # HTML templates
│   │   ├── auth/           # Authentication templates
│   │   └── pages/          # Page templates
│   ├── models.py           # Database models
│   └── urls.py             # URL routing
├── services/               # External service integrations
│   └── nfl.py             # NFL data service
├── cache/                  # Data cache directory
├── secretbox/             # Django project settings
└── requirements.txt       # Python dependencies
```

## 🔧 Configuration

### Environment Variables
- `NFL_SEASON`: Current NFL season (default: 2025)
- `CACHE_DIR`: Cache directory path
- `USE_DB_CACHE`: Enable database caching

### Settings
- Debug mode enabled for development
- SQLite database for local development
- Static files configuration
- Authentication settings

## 📈 Data Flow

1. **Data Ingestion**: NFL data fetched via nflreadpy API
2. **Caching**: Data stored in Parquet files for efficiency
3. **Processing**: Data processed with Pandas/Polars
4. **Storage**: Processed data stored in SQLite database
5. **Presentation**: Data displayed through Django templates
6. **Predictions**: ML models generate predictions for props and outcomes

## 🎮 Usage

### Landing Page
- View current week's games
- Navigate to specific weeks
- Access game details

### Week View
- Browse all games for a specific week
- View starting quarterback statistics
- Access previous week performance data

### Game Detail
- Detailed game information
- Team matchup analysis
- Game timing and status

## 🔮 Future Enhancements

- Real-time data updates
- Advanced ML model improvements
- User prediction tracking
- Social features and leaderboards
- Mobile app development
- API endpoints for external integrations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **nflreadpy**: For providing comprehensive NFL data
- **Django**: For the robust web framework
- **Pandas/Polars**: For efficient data processing
- **NFL**: For the amazing sport and data

---

**SecretBox** - Where NFL analytics meets machine learning. Built with ❤️ for football fans and data enthusiasts.

------

command to refresh the lines

python3 manage.py refresh_player_props