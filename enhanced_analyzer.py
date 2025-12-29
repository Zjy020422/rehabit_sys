from sklearn.preprocessing import StandardScaler
import sqlite3
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import json
from datetime import datetime
from plotly.subplots import make_subplots
import plotly.graph_objects as go

class EnhancedRehabilitationAnalyzer:
    def __init__(self,db_path = 'rehabilitation_data.db'):
        self.db_path = db_path 
        self.scaler=StandardScaler()
    def load_session_data(self,session_id):
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT timestamp, test_type, force_value, angle_value
            FROM sensor_data
            WHERE session_id = ?
            ORDER BY timestamp
        '''
        df = pd.read_sql_query(query,conn,params=(session_id,))
        conn.close()

        if not df.empty:
            df['timestamp']=pd.to_datetime(df['timestamp'])
            df=df.fillna(0)

        return df
    def load_user_historical_data(self,user_id,days=30):
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT s.timestamp, s.test_type, s.force_value, s.angle_value, s.session_id
            FROM sensor_data s
            JOIN training_sessions ts ON s.session_id = ts.session_id
            WHERE ts.user_id = ?
            AND s.timestamp >= date('now', '-{} days')
            ORDER BY s.timestamp 
        '''.format(days)

        df = pd.read_sql_query(query, conn, params=(user_id,))
        conn.close()
        if not df.empty:
            df['timestamp']=pd.to_datetime(df['timestamp'])
            df=df.fillna(0)
        return df
    def basic_statistical_analysis(self, df):
        if df.empty:
            return{'error':'No data found'}
        analysis = {}
        for test_type in df['test_type'].unique():
            test_data = df[df['test_type'] == test_type]
            type_analysis = {}
            
            if 'force_value' in test_data.columns and test_data['force_value'].notna().any():
                force_data = test_data['force_value'].dropna()
                type_analysis['force'] = {
                    'mean': float(force_data.mean()),
                    'std': float(force_data.std()),
                    'min': float(force_data.min()),
                    'max': float(force_data.max()),
                    'median': float(force_data.median()),
                    'count': int(len(force_data))
                }
            
            if 'angle_value' in test_data.columns and test_data['angle_value'].notna().any():
                angle_data = test_data['angle_value'].dropna()
                type_analysis['angle'] = {
                    'mean': float(angle_data.mean()),
                    'std': float(angle_data.std()),
                    'min': float(angle_data.min()),
                    'max': float(angle_data.max()),
                    'median': float(angle_data.median()),
                    'count': int(len(angle_data))
                }
            
            analysis[test_type] = type_analysis
        
        return analysis
    
    def trend_analysis(self,df):

        if df.empty:
            return {"error": "数据为空"}
        if 'session_id' in df.columns:
            trends = {}
            for test_type in df['test_type'].unique():
                print(test_type)
                type_analysis = {}

                if test_type == 'force test':
                    ydf = df[df['test_type'] == 'force test']
                    #print(ydf)
                    session_trends = []
                    for session_id in ydf['session_id'].unique():
                        session_data = ydf[ydf['session_id'] == session_id]

                        session_analysis = {
                        'session_id': session_id,
                        'timestamp': session_data['timestamp'].min().isoformat(),
                        'duration_minutes': (session_data['timestamp'].max() - 
                                        session_data['timestamp'].min()).total_seconds() / 60
                    }
                        session_analysis['avg_force'] = float(session_data['force_value'].mean())
                        session_analysis['max_force'] = float(session_data['force_value'].max())
                        session_trends.append(session_analysis)
                    type_analysis['session_trends'] = session_trends 
                    ydf_sorted = ydf.sort_values('timestamp')
                    if len(ydf_sorted)>10:
                        mid_point = len(ydf_sorted) // 2
                        first_half = ydf_sorted.iloc[:mid_point]
                        second_half = ydf_sorted.iloc[mid_point:]
                        type_analysis['overall_trends'] = {}
                        force_change = (second_half['force_value'].mean() - first_half['force_value'].mean())
                        type_analysis['overall_trends']['force_improvement'] = {
                            'change': float(force_change),
                            'percentage': float((force_change / first_half['force_value'].mean()) * 100) if first_half['force_value'].mean() != 0 else 0
                        }
                    #trends[test_type] = type_analysis
                
                elif test_type == 'angle test':
                    ydf = df[df['test_type'] == 'angle test']
                    #print(ydf)
                    session_trends = []
                    for session_id in ydf['session_id'].unique():
                        session_data = ydf[ydf['session_id'] == session_id]

                        session_analysis = {
                        'session_id': session_id,
                        'timestamp': session_data['timestamp'].min().isoformat(),
                        'duration_minutes': (session_data['timestamp'].max() - 
                                        session_data['timestamp'].min()).total_seconds() / 60
                    }
                        session_analysis['avg_angle'] = float(session_data['angle_value'].mean())
                        session_analysis['max_angle'] = float(session_data['angle_value'].max())
                        session_trends.append(session_analysis)
                    type_analysis['session_trends'] = session_trends 
                    ydf_sorted = ydf.sort_values('timestamp')
                    if len(ydf_sorted)>10:
                        mid_point = len(ydf_sorted) // 2
                        first_half = ydf_sorted.iloc[:mid_point]
                        second_half = ydf_sorted.iloc[mid_point:]
                        type_analysis['overall_trends'] = {}
                        angle_change = (second_half['angle_value'].mean() - first_half['angle_value'].mean())

                        type_analysis['overall_trends']['angle_improvement'] = {
                            'change': float(angle_change),
                            'percentage': float((angle_change / first_half['angle_value'].mean()) * 100) if first_half['angle_value'].mean() != 0 else 0
                        }
                    #trends[test_type] = type_analysis

                    
                elif test_type == 'force and angle test':
                    ydf = df[df['test_type'] == 'force and angle test']
                    #print(ydf)
                    session_trends = []
                    for session_id in ydf['session_id'].unique():
                        session_data = ydf[ydf['session_id'] == session_id]

                        session_analysis = {
                        'session_id': session_id,
                        'timestamp': session_data['timestamp'].min().isoformat(),
                        'duration_minutes': (session_data['timestamp'].max() - 
                                        session_data['timestamp'].min()).total_seconds() / 60
                    }
                        session_analysis['avg_angle'] = float(session_data['angle_value'].mean())
                        session_analysis['max_angle'] = float(session_data['angle_value'].max())
                        session_analysis['avg_force'] = float(session_data['force_value'].mean())
                        session_analysis['max_force'] = float(session_data['force_value'].max())
                        session_trends.append(session_analysis)
                    type_analysis['session_trends'] = session_trends 
                    ydf_sorted = ydf.sort_values('timestamp')
                    if len(ydf_sorted)>10:
                        mid_point = len(ydf_sorted) // 2
                        first_half = ydf_sorted.iloc[:mid_point]
                        second_half = ydf_sorted.iloc[mid_point:]
                        type_analysis['overall_trends'] = {}
                        angle_change = (second_half['angle_value'].mean() - first_half['angle_value'].mean())
                        force_change = (second_half['force_value'].mean() - first_half['force_value'].mean())

                        type_analysis['overall_trends']['force_improvement'] = {
                            'change': float(force_change),
                            'percentage': float((force_change / first_half['force_value'].mean()) * 100) if first_half['force_value'].mean() != 0 else 0
                        }
                        type_analysis['overall_trends']['angle_improvement'] = {
                            'change': float(angle_change),
                            'percentage': float((angle_change / first_half['angle_value'].mean()) * 100) if first_half['angle_value'].mean() != 0 else 0
                        }
                    
                
                trends[test_type] = type_analysis
                #print(trends)

            return trends
        
    def performance_clustering(self,df):
        if 'session_id' in df.columns:
            clustering_results_all={}
            for test_type in df['test_type'].unique():
                print(test_type)
                if test_type == 'force test':
                    ydf = df[df['test_type'] == test_type]
                    features = ['force_value']
                elif test_type == 'angle_test':
                    ydf=df[df['test_type'] == test_type]
                    features = ['angle_value']
                elif test_type == 'force and angle_test':
                    ydf=df[df['test_type'] == test_type]
                    features = ['force_value', 'angle_value']
                if df.empty or len(df)<=15: 
                    return {'Data insufficient for clustering'}
                numerical_data=ydf[features].fillna(0)
                scaled_data = self.scaler.fit_transform(numerical_data)
                max_clusters = min(5,len(numerical_data)-1)
                best_k=2
                best_score=0

                for k in range(2,max_clusters+1):
                    if k<=len(numerical_data):
                        kmeans = KMeans(n_clusters=k,random_state=42,n_init=10)
                        cluster_labels = kmeans.fit_predict(scaled_data)
                        if len(set(cluster_labels))>1:
                            score = silhouette_score(scaled_data,cluster_labels)
                            if score>best_score:
                                best_score = score
                                best_k=k
                kmeans= KMeans (n_clusters=best_k,random_state=42,n_init=10)
                cluster_labels = kmeans.fit_predict(scaled_data)

                clustering_results = {
                    'n_clusters' : int(best_k),
                    'silhoutte_score':float(best_score),
                    'cluster_centers':kmeans.cluster_centers_.tolist(),
                    'cluster_lables':cluster_labels.tolist()
                }
                clustering_results_all[test_type]=clustering_results

            return clustering_results_all
    def generate_performance_score(self,df):
        type={}
        for test_type in df['test_type'].unique():
            if test_type == 'angle test':
                score = (max(df['angle_value'].max()-df['angle_value'])/90)*100
                print(score)
            elif test_type == 'force test':
                score = (300-df['force_value'].max())/300
                print(score)
            elif test_type == 'force and angle test':
                ydf = df[df['force_value']>10]
                ydf_sorted = ydf.sort_values('timestamp')
                angle = ydf['angle_value'].iloc[0]
                angle_score = (df['angle_value'].max()-angle)/(df['angle_value'].max()-df['angle_value'].min())*100
                force_score = (300-df['force_value'].max())/300
                score = (angle_score+force_score)/2 
            type[test_type] = score
    
        
        return {
            'score':type,
            'grade':self.get_performance_grade(type)
        }
    def get_performance_grade(self,dict):
        sum = 0
        a=0
        for test_type in dict:
            score = dict[test_type]
            sum = sum+score
            a=a+1
        
        score = sum/a
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        else:
            return 'D'
        
    def comprehensive_analysis(self, session_id):
        """
        综合分析
        :param session_id: 会话ID
        :return: 完整的分析结果
        """
        # 加载数据
        df = self.load_session_data(session_id)
        
        if df.empty:
            return {"error": "没有找到会话数据"}
        
        # 执行各种分析
        analysis_results = {
            'session_id': session_id,
            'data_summary': {
                'total_records': len(df),
                'test_types': df['test_type'].unique().tolist(),
                'time_range': {
                    'start': df['timestamp'].min().isoformat(),
                    'end': df['timestamp'].max().isoformat(),
                    'duration_minutes': (df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 60
                }
            },
            'statistical_analysis': self.basic_statistical_analysis(df),
            'trend_analysis': self.trend_analysis(df),
            'clustering_analysis': self.performance_clustering(df),
            'performance_score': self.generate_performance_score(df),
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # 保存分析结果到数据库
        self.save_analysis_results(session_id, 'comprehensive', analysis_results)
        
        return analysis_results
    
    def save_analysis_results(self, session_id, analysis_type, results):
        """
        保存分析结果到数据库
        :param session_id: 会话ID
        :param analysis_type: 分析类型
        :param results: 分析结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO final_data (session_id, analysis_type, results)
                VALUES (?, ?, ?)
            ''', (session_id, analysis_type, json.dumps(results, ensure_ascii=False)))
            
            conn.commit()
            print(f"分析结果已保存: {session_id} - {analysis_type}")
        except Exception as e:
            print(f"保存分析结果失败: {e}")
        finally:
            conn.close()
    
    def create_visualization(self, df, save_path=None):
        """
        创建数据可视化图表
        :param df: 数据框
        :param save_path: 保存路径
        :return: 图表对象
        """
        if df.empty:
            return None
        
        # 创建子图
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Force Time Graph', 'Angle Time Graph', 
                          'Force Time Scatter Plot', 'Angle Time Scatter Plot'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # 时间序列图 - 拉力
        if df['force_value'].notna().any():
            force_data = df[df['force_value'].notna()]
            fig.add_trace(
                go.Scatter(x=force_data['timestamp'], y=force_data['force_value'],
                          mode='lines+markers', name='Force (N)', line=dict(color='blue')),
                row=1, col=1
            )
        
        # 时间序列图 - 角度
        if df['angle_value'].notna().any():
            angle_data = df[df['angle_value'].notna()]
            fig.add_trace(
                go.Scatter(x=angle_data['timestamp'], y=angle_data['angle_value'],
                          mode='lines+markers', name='Angle (°)', line=dict(color='red')),
                row=1, col=2
            )
        
        # 散点图 - 拉力vs角度
        if df['force_value'].notna().any() and df['angle_value'].notna().any():
            combined_data = df.dropna(subset=['force_value', 'angle_value'])
            if not combined_data.empty:
                fig.add_trace(
                    go.Scatter(x=combined_data['force_value'], y=combined_data['angle_value'],
                              mode='markers', name='Force - Angle Relationship', 
                              marker=dict(color='green', size=8)),
                    row=2, col=1
                )
        
        # 直方图 - 数据分布
        if df['force_value'].notna().any():
            fig.add_trace(
                go.Histogram(x=df['force_value'].dropna(), name='Force distribution', 
                           marker=dict(color='lightblue'), opacity=0.7),
                row=2, col=2
            )
        
        # 更新布局
        fig.update_layout(
            title='Rehabilitation Data Analysis Figure',
            height=800,
            showlegend=True
        )
        
        # 更新坐标轴标签
        fig.update_xaxes(title_text="Time", row=1, col=1)
        fig.update_yaxes(title_text="Force (N)", row=1, col=1)
        fig.update_xaxes(title_text="Time", row=1, col=2)
        fig.update_yaxes(title_text="Angle (°)", row=1, col=2)
        fig.update_xaxes(title_text="Force (N)", row=2, col=1)
        fig.update_yaxes(title_text="Angle (°)", row=2, col=1)
        fig.update_xaxes(title_text="Force (N)", row=2, col=2)
        fig.update_yaxes(title_text="Frequency", row=2, col=2)
        
        if save_path:
            fig.write_html(save_path)
            print(f"图表已保存到: {save_path}")
        return fig   
    def generate_comparison_analysis(self,user_id, days=30):
        """
        生成用户历史对比分析
        :param user_id: 用户ID
        :param days: 对比天数
        :return: 对比分析结果
        """
        df = self.load_user_historical_data(user_id, days)
        
        if df.empty:
            return {"error": "没有足够的历史数据"}
        
        # 按会话分组进行对比分析
        session_comparison = {}
        sessions = df['session_id'].unique()
        
        if len(sessions) < 2:
            return {"error": "需要至少2个训练会话进行对比"}
        
        session_stats = []
        for session_id in sessions:
            session_data = df[df['session_id'] == session_id]
            
            stats = {
                'session_id': session_id,
                'date': session_data['timestamp'].min().date().isoformat(),
                'duration': (session_data['timestamp'].max() - 
                           session_data['timestamp'].min()).total_seconds() / 60
            }
            type = {}
            for test_type in session_data['test_type'].unique():
                values={}
                print(test_type)
                ydf = session_data[session_data['test_type'] == test_type]
                if test_type == 'angle test':
                    values['angle_value'] = ydf['angle_value'].min()
                elif test_type == 'force test':
                    values['force_value'] = ydf['force_value'].max()        
                elif test_type == 'force angle test':
                    ydf = df[df['force_value']>0]
                    ydf_sorted = ydf.sort_values('timestamp')
                    values['angle_value'] = float(ydf_sorted['angle_value'].iloc[0])
                    values['force_value'] = ydf_sorted['force_value'].max()
                type[test_type]=values
                stats['values'] =type
            session_stats.append(stats)
        session_stats.sort(key=lambda x: x['date'])
        # 计算改进趋势
        improvements = {}
        improvement = {}
        if len(session_stats) >= 2:
            first_session = session_stats[0]
            last_session = session_stats[-1]
            type = {}
            for test_type in first_session['values'].keys():
                if test_type == 'angle test':
                    if 'angle value' in last_session['values'].keys():
                        #print(last_session['values']['angle_test']['angle_value'])
                        improvement['angle'] = first_session['values'][test_type]['angle_value'] - last_session['values'][test_type]['angle_value']
                elif test_type == 'force test':    
                    if 'force test' in last_session['values'].keys():
                        improvement['force'] = first_session['values'][test_type]['force_value'] - last_session['values'][test_type]['force_value']
                elif test_type == 'force angle test':
                    if 'force angle value' in last_session['values'].keys():
                        improvement['angle'] = first_session['values'][test_type]['angle_value'] - last_session['values'][test_type]['angle_value']
                        improvement['force'] = first_session['values'][test_type]['force_value'] - last_session['values'][test_type]['force_value']
                improvements[test_type] = improvement

        return {
            'user_id': user_id,
            'analysis_period_days': days,
            'total_sessions': len(sessions),
            'session_statistics': session_stats,
            'improvements': improvements,
        }

            
    
if __name__ == '__main__':
    #analysis = RehabilitationAnalyzer()
    '''df = analysis.load_session_data('session_20250705_161141')
    
    a = analysis.load_user_historical_data('test_user')
    #a = analysis.basic_statistical_analysis(df)
    #print(a)
    a = analysis.performance_clustering(a)
    a= analysis.generate_performance_score(df)
    a= analysis.comprehensive_analysis('session_20250705_161141')
    a= analysis.create_visualization(df,f"analysis_session_20250705_161141.html")'''
    #a = analysis.generate_comparison_analysis('test_user')
    #print(a)


    


