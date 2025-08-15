# Fix That Prompt - Leaderboard Dashboard

A beautiful, real-time leaderboard dashboard for the Fix That Prompt game.

## Features

- 🏆 **Real-time Leaderboard**: Shows top players with scores
- 📊 **Game Statistics**: Total players, completed games, average scores
- 🎨 **Beautiful UI**: Modern design with Tailwind CSS
- 🔄 **Auto-refresh**: Updates every 30 seconds
- 📱 **Responsive**: Works on desktop and mobile
- 🏅 **Trophy System**: Gold, silver, bronze medals for top 3

## Quick Start

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export DYNAMODB_TABLE_NAME=fix-that-prompt-leaderboard
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   ```

3. **Run the dashboard:**
   ```bash
   python app.py
   ```

4. **Open in browser:**
   ```
   http://localhost:5001
   ```

### Docker Deployment

1. **Build the image:**
   ```bash
   docker build -t fix-that-prompt-dashboard .
   ```

2. **Run the container:**
   ```bash
   docker run -p 5000:5000 \
     -e DYNAMODB_TABLE_NAME=fix-that-prompt-leaderboard \
     -e AWS_ACCESS_KEY_ID=your_access_key \
     -e AWS_SECRET_ACCESS_KEY=your_secret_key \
     -e AWS_DEFAULT_REGION=us-east-1 \
     fix-that-prompt-dashboard
   ```

## API Endpoints

### GET `/api/leaderboard`
Returns the current leaderboard data.

**Response:**
```json
{
  "success": true,
  "players": [
    {
      "username": "player1",
      "final_score": 25,
      "game_status": "completed",
      "completed_at": "2024-01-15T10:30:00Z",
      "rounds_played": 3
    }
  ],
  "total_players": 1,
  "last_updated": "2024-01-15T10:35:00Z"
}
```

### GET `/api/stats`
Returns game statistics.

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_completed_games": 10,
    "active_games": 2,
    "average_score": 18.5,
    "highest_score": 30,
    "lowest_score": 5
  }
}
```

## Dashboard Features

### 📈 **Statistics Cards**
- **Total Players**: Number of completed games
- **Completed Games**: Games that finished successfully
- **Active Games**: Currently ongoing games
- **Average Score**: Mean score across all players
- **Top Score**: Highest score achieved

### 🏆 **Leaderboard Table**
- **Rank**: Position with trophy icons
- **Player**: Username
- **Score**: Final game score
- **Rounds**: Number of rounds played
- **Completed**: Date when game finished

### 🔄 **Auto-refresh**
- Updates every 30 seconds automatically
- Manual refresh button available
- Shows last updated timestamp

## Customization

### **Styling**
The dashboard uses Tailwind CSS. You can customize:
- Colors in the CSS variables
- Layout in the HTML structure
- Icons from Font Awesome

### **Data Fields**
Modify the API endpoints to include additional fields:
- Game duration
- Prompt categories
- Player achievements
- Custom metrics

## Deployment Options

### **AWS ECS**
Deploy alongside your main game using the same CDK stack.

### **AWS Lambda**
Convert to serverless functions for cost optimization.

### **Static Hosting**
Use S3 + CloudFront for static hosting with API Gateway.

## Security

- **IAM Roles**: Use least privilege access to DynamoDB
- **CORS**: Configure if needed for cross-origin requests
- **Rate Limiting**: Consider adding rate limiting for API endpoints

## Monitoring

- **CloudWatch Logs**: Application logs
- **CloudWatch Metrics**: API performance
- **Health Checks**: Endpoint monitoring
