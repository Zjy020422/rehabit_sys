import os
from openai import OpenAI
import json
from datetime import datetime
from typing import Dict,List,Any
import sqlite3
import pandas as pd
class EnhancedGPTRehabilitationAdvisor:

    
    def __init__(self, api_key = 'sk-cb387c428d9343328cea734e6ae0f9f5',db_path="rehabilitation_data.db",model="deepseek-chat"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.db_path = db_path
        self.model = model
        self.client=None

        self.client = OpenAI(api_key=self.api_key,base_url=f"https://api.deepseek.com")

    def create_analysis_prompt(self,analysis_data:Dict, user_profile:Dict=None):
        ''' Create a prompt that can be used to generate an analysis
            "param analysis data: 分析数据
            param user profile: 用户信息'''

        prompt = f"""
    ##patient message
    {f"Age: {user_profile.get('age', 'unknown')}" if user_profile else ""}
    {f"Gender: {user_profile.get('gender', 'unknown')}" if user_profile else ""}
    {f"Height: {user_profile.get('height', 'Unknown')}" if user_profile else ""}
    {f"Weight: {user_profile.get('weight', 'Unknown')}" if user_profile else ""}
    {f"Rehabilitation Stage: {user_profile.get('rehabilitation_stage', 'Unknown')}" if user_profile else ""}
    {f"Main Problems: {user_profile.get('main_issues', 'Unknown')}" if user_profile else ""}

    ###Base analyze information
    - Training Duration: {analysis_data.get('data_summary', {}).get('time_range', {}).get('duration_minutes', 0):.1f} minutes
    - Data Record: {analysis_data.get('data_summary', {}).get('total_records', 0)} 条
    - Test Type {', '.join(analysis_data.get('data_summary', {}).get('test_types', []))}

    ### Performance Score
    - General Performance: {analysis_data.get('performance_score', {}).get('overall_score', 0):.1f}/100
    - Grade: {analysis_data.get('performance_score', {}).get('grade', 'N/A')}
        
    ### Statistical Analysis
    {json.dumps(analysis_data.get('statistical_analysis', {}), ensure_ascii=False, indent=2)}

    ### Trend Analysis
    {json.dumps(analysis_data.get('trend_analysis', {}), ensure_ascii=False, indent=2)}

    ### Cluster Analysis
    {json.dumps(analysis_data.get('clustering_analysis', {}), ensure_ascii=False, indent=2)}

    ## Please provide the following suggestions:

    1. Training performance evaluation
        -Overall evaluation of the patient's current training performance
        -Strengths and areas for improvement
    2. Specific training suggestions
        -Specific suggestions for tensile training (if there is tensile data available)
        -Specific suggestions for angle training (if angle data is available)
        -Suggestions for adjusting training intensity
    3. Training Plan Optimization
        -Specific parameter suggestions for the next training session
        -Suggestions for training frequency and duration
        -Progressive Training Program
    4. Precautions
        -Safety precautions to be taken during the training process
        -Possible risk warning
    5. Rehabilitation progress estimation
        -Estimate rehabilitation progress based on current data
        -Estimated time to achieve rehabilitation goals
        Please reply in professional and in english but understandable language to ensure that the suggestions are actionable.
    """
        return prompt
    
    def create_comparison_prompt(self, comparison_data:dict, user_profile=None) -> str:
        """
        创建对比分析提示词
        :param comparison_data: 对比数据
        :param user_profile: 用户档案
        :return: 格式化的提示词
        """
        prompt = f"""
        You are a professional physiotherapist and doctor, please provide a rehabilitation progress assessment and follow-up recommendations based on a comparative analysis of the patient's historical training data.

        ## Patient Information
        {f"Age: {user_profile.get('age', 'unknown')}" if user_profile else ""}
        {f"Rehabilitation Stage: {user_profile.get('rehabilitation_stage', 'unknown')}" if user_profile else ""}

        ##Historical Training Data Comparison and Analysis

        ### Overal Situation
        - Analysis Timeframe: {comparison_data.get('analysis_period_days', 0)} days
        - Total Training Sessions: {comparison_data.get('total_sessions', 0)} times

        ### Data Improvements
        {json.dumps(comparison_data.get('improvements', {}), ensure_ascii=False, indent=2)}

        ### Overall Trend
        {json.dumps(comparison_data.get('overall_trend', {}), ensure_ascii=False, indent=2)}

        ### Session Data details
        {json.dumps(comparison_data.get('session_statistics', [])[:5], ensure_ascii=False, indent=2)}

        ## Please provide the following analysis and suggestions:

        1. Rehabilitation progress assessment
        -Overall rehabilitation progress evaluation
        -Improvement of different parts of training

        2. Training Effect Analysis
        -What aspects have shown significant improvement
        -What aspects need to be strengthened

        3. Personalized suggestions
        -Personalized training adjustment based on historical data
        -Suggestions for specialized training for weaker parts of training

        4. Future Training Plan
        -Setting training objectives for the next stage
        -Suggestions for adjusting training intensity and frequency

        5. Incentives and Encouragement
        -Recognition of patients' progress
        -Encouragement words for continuing to persist in training

        Please provide professional, warm, and motivating advice in english.
        """
        return prompt


    def generate_recommendations(self, analysis_data, user_profile=None):
        """
        生成康复训练建议
        :param analysis_data: 分析数据
        :param user_profile: 用户档案
        :return: 生成的建议
        """
        #try:
            # 创建提示词
        prompt = self.create_analysis_prompt(analysis_data, user_profile)
        print(prompt)
            
            # 调用GPT API，如果失败则使用模拟响应
        try:
            if self.client:
                response = self.call_openai_api(prompt)
                print(response)
            '''else:
                response = self.generate_mock_recommendations(analysis_data)'''
        except (ConnectionError, Exception):
                # 网络错误或其他API错误时使用模拟响应
            print("API调用失败，使用模拟建议生成器")
            #response = self.generate_mock_recommendations(analysis_data)
            
        session_id = analysis_data.get('session_id')
        if session_id:
            self.save_recommendations(session_id, 'analysis_based', response)
            
        return {
                'type': 'analysis_based_recommendations',
                'session_id': session_id,
                'recommendations': response,
                'generated_at': datetime.now().isoformat()
            }
            
        '''except Exception as e:
            print(f"生成建议时发生错误: {e}")'''
    

    def generate_comparison_recommendations(self, comparison_data: Dict, user_profile: Dict = None) -> Dict:
        """
        基于对比数据生成建议
        :param comparison_data: 对比数据
        :param user_profile: 用户档案
        :return: 生成的建议
        """
        try:
            # 创建提示词
            prompt = self.create_comparison_prompt(comparison_data, user_profile)
            
            # 调用GPT API，如果失败则使用模拟响应
            try:
                if self.client:
                    response = self.call_openai_api(prompt)
                else:
                    response = self.generate_mock_comparison_recommendations(comparison_data)
            except (ConnectionError, Exception):
                # 网络错误或其他API错误时使用模拟响应
                print("API调用失败，使用模拟建议生成器")
                response = self.generate_mock_comparison_recommendations(comparison_data)
            
            return {
                'type': 'comparison_based_recommendations',
                'user_id': comparison_data.get('user_id'),
                'recommendations': response,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"生成对比建议时发生错误: {e}")

    def call_openai_api(self,prompt):
        response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一位专业的康复训练专家，擅长分析康复数据并提供专业建议。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=2000,
                    temperature=0.7
                )
        return response.choices[0].message.content.strip()
    
    def save_recommendations(self,session_id,recommendations_type,content):

        conn=sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
                UPDATE analysis_results 
                SET recommendations = ?
                WHERE session_id = ? AND analysis_type = ?
            ''', (content, session_id,recommendations_type))
        conn.close()

    def get_user_profile(self,user_id):
        return {
            'age': 35,
            'gender': '男',
            'rehabilitation_stage': '中期康复',
            'main_issues': '膝关节功能恢复',
            'training_experience': '3个月'
        }

    def generate_daily_report(self,user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取今日训练数据
        cursor.execute('''
            SELECT s.session_id, s.start_time, s.end_time, s.duration
            FROM training_sessions s
            WHERE s.user_id = ? 
            AND date(s.start_time) = date('now')
            ORDER BY s.start_time DESC
        ''', (user_id,))

        today_sessions = cursor.fetchall()
        conn.close()

        if not today_sessions:
            return {
                'message': '今日暂无训练数据',
                'recommendation': '建议进行适量的康复训练以保持训练连续性。'
            }
        
        # 构建每日报告数据
        total_duration = sum([session[3] or 0 for session in today_sessions])
        session_count = len(today_sessions)
        
        report_data = {
            'date': datetime.now().date().isoformat(),
            'session_count': session_count,
            'total_duration_minutes': total_duration / 60 if total_duration else 0,
            'sessions': [
                {
                    'session_id': session[0],
                    'start_time': session[1],
                    'end_time': session[2],
                    'duration_minutes': (session[3] / 60) if session[3] else 0
                }
                for session in today_sessions
            ]
        }
        
        # 生成每日建议
        prompt = f"""
As a rehabilitation training expert, please provide a brief daily report and recommendations in english based on the patient's training situation today.

Todays training report：
- Training count：{session_count} Times
- Total training duration：{report_data['total_duration_minutes']:.1f} Minutes

Please provide：
1. Brief analysis and evaluation of todays training（Under 50 words）
2. Training suggestions for tomorrow（Under 50 words）
3. Words of motivation（Under 30 words）

Please keep tone concise, professional, and warm.
"""
        daily_advice = self.call_openai_api(prompt)
        print(daily_advice)
        return {
                'type': 'daily_report',
                'date': report_data['date'],
                'training_summary': report_data,
                'advice': daily_advice,
                'generated_at': datetime.now().isoformat()
            }
    
    def generate_weekly_summary(self, user_id: str) -> Dict:
        """
        生成周训练总结
        :param user_id: 用户ID
        :return: 周总结
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取本周训练数据
        cursor.execute('''
            SELECT s.session_id, s.start_time, s.duration,
                   COUNT(sd.id) as data_points
            FROM training_sessions s
            LEFT JOIN sensor_data sd ON s.session_id = sd.session_id
            WHERE s.user_id = ? 
            AND s.start_time >= date('now', '-7 days')
            GROUP BY s.session_id
            ORDER BY s.start_time
        ''', (user_id,))
        
        week_sessions = cursor.fetchall()
        conn.close()
        
        if not week_sessions:
            return {
                'message': 'No training data available this week',
                'recommendation': 'It is recommended to develop a regular training plan and train 3-4 times a week'
            }
        
        # 计算周统计
        total_sessions = len(week_sessions)
        total_duration = sum([session[2] or 0 for session in week_sessions])
        avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
        
        weekly_data = {
            'week_start': (datetime.now().date() - pd.Timedelta(days=7)).isoformat(),
            'week_end': datetime.now().date().isoformat(),
            'total_sessions': total_sessions,
            'total_duration_hours': total_duration / 3600 if total_duration else 0,
            'average_session_duration_minutes': avg_duration / 60 if avg_duration else 0,
            'training_frequency': total_sessions / 7  # 每日平均训练次数
        }
        prompt = f"""

As a rehabilitation training expert, please provide a weekly summary and next week's recommendations in english based on the patient's training situation this week.

This weeks training situation:：
- Training sessions：{total_sessions} times
- Total duration：{weekly_data['total_duration_hours']:.1f} Hours
- Average session duration：{weekly_data['average_session_duration_minutes']:.1f} Minutes
- Training frequency：{weekly_data['training_frequency']:.1f} Times/days


Please provide:
1. Summary of this week's training performance (within 100 words)
2. Suggestions for next week's training plan (within 100 words)
3. Long term rehabilitation recommendations (within 80 words)
Maintain a professional and encouraging tone.
"""
        weekly_advice = self.call_openai_api(prompt)
        print(weekly_advice)
        return {
                'type': 'weekly_summary',
                'week_period': f"{weekly_data['week_start']} 至 {weekly_data['week_end']}",
                'statistics': weekly_data,
                'summary_advice': weekly_advice,
                'generated_at': datetime.now().isoformat()
            }


'''
advisor = GPTRehabilitationAdvisor()
mock_analysis_data = {
        'session_id': 'session_20250630_155418',
        'data_summary': {
            'total_records': 120,
            'test_types': ['force test', 'angle test'],
            'time_range': {
                'duration_minutes': 18.5
            }
        },
        'performance_score': {
            'overall_score': 78.5,
            'grade': 'B',
            'completeness_score': 95.0
        },
        'statistical_analysis': {
            'force test': {
                'force': {
                    'mean': 55.2,
                    'std': 8.3,
                    'min': 35.1,
                    'max': 72.8
                }
            }
        },
        'anomaly_detection': {
            'anomaly_percentage': 5.2
        }}
user_message={
        'user_id': 'test_user',
        'Age': 30,
        'Gender': 'Male',
        'Height': 180.0,
        'Weight': 70.0,
        'Rehabilitation_Stage': 'A',
        'Main problem':'force not enough'
    }
    '''
'''recommendations = advisor.generate_recommendations(mock_analysis_data,user_message)
daily_report = advisor.generate_daily_report('test_user')
weekly_report = advisor.generate_weekly_summary('test_user')'''
#print(daily_report)
#print(weekly_report)
