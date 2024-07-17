import streamlit as st
import praw
import google.generativeai as genai
import json
import prawcore
import pandas as pd

def get_trending_posts_with_comments(reddit_client_id, reddit_client_secret, reddit_user_agent, subreddit_name, num_posts=10):
    try:
        reddit = praw.Reddit(
            client_id=reddit_client_id,
            client_secret=reddit_client_secret,
            user_agent=reddit_user_agent
        )
        subreddit = reddit.subreddit(subreddit_name)
        top_posts = list(subreddit.top(time_filter="day", limit=num_posts))
        all_posts_data = []

        for post in top_posts:
            post.comments.replace_more(limit=0)
            comments = post.comments.list()
            comments.sort(key=lambda x: x.score, reverse=True)
            top_comments = comments[:min(10, len(comments))]
            
            formatted_output = f"Title: {post.title}\n"
            formatted_output += f"Post: {post.selftext if post.selftext else '[No body text]'}\n"
            for i, comment in enumerate(top_comments, 1):
                formatted_output += f"Comment {i}: {comment.body}\n"
            all_posts_data.append(formatted_output)

        return all_posts_data
    except praw.exceptions.PRAWException as e:
        st.error(f"PRAW Error: {str(e)}")
    except prawcore.exceptions.ResponseException as e:
        st.error(f"ResponseException: {str(e)}. Please check your Reddit API credentials.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
    return None

def convert_to_qa(gemini_api_key, information):
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash',
                                  system_instruction="""You are helpful assistant, who can structure a raw information to a set of question answer. 
                                  User is very uninterested person. Your job is to intrigue his curiosity by converting the raw information. 
                                  Question can be used to grab attention, clickbait. It should be short, precise and attention grabbing.
                                  Answers can be long, but should reply the query in question.
                                  Your output will be in below json list format [{"question" : question, "answer" : answer},]""",
                                  generation_config={"response_mime_type": "application/json"})

    prompt = f"Raw_data : ====================\n {information}\n====================\n"
    response = model.generate_content(prompt)

    try:
        qa_pairs = json.loads(response.text)
        return qa_pairs
    except json.JSONDecodeError:
        st.error("Error: Unable to parse JSON response from Gemini API")
        return None

def save_to_excel(qa_data, filename="reddit_qa.xlsx"):
    flat_data = [item for sublist in qa_data for item in sublist]
    df = pd.DataFrame(flat_data)
    df.to_excel(filename, index=False)
    st.success(f"Data saved to {filename}")
    return df

def main():
    st.set_page_config(page_title="Reddit Scraper", page_icon="🤖", layout="wide")
    st.title("Reddit Scraper with Q&A Conversion")

    # Sidebar for inputs
    with st.sidebar:
        st.header("API Settings")
        reddit_client_id = st.text_input("Reddit Client ID", type="password")
        reddit_client_secret = st.text_input("Reddit Client Secret", type="password")
        reddit_user_agent = st.text_input("Reddit User Agent")
        gemini_api_key = st.text_input("Gemini API Key", type="password")

        st.header("Scraper Settings")
        subreddit = st.text_input("Subreddit", value="python")
        num_posts = st.number_input("Number of Posts", min_value=1, max_value=100, value=10)

    # Main body
    if st.button("Start Scraping"):
        if not all([reddit_client_id, reddit_client_secret, reddit_user_agent, gemini_api_key, subreddit]):
            st.error("Please fill in all the required fields in the sidebar.")
        else:
            with st.spinner("Scraping posts..."):
                reddit_content = get_trending_posts_with_comments(
                    reddit_client_id, reddit_client_secret, reddit_user_agent, subreddit, num_posts
                )

            if reddit_content:
                st.success(f"Retrieved {len(reddit_content)} posts from r/{subreddit}.")
                
                progress_bar = st.progress(0)
                all_qa_pairs = []

                for i, post_content in enumerate(reddit_content):
                    with st.spinner(f"Converting post {i+1}/{len(reddit_content)} to Q&A format..."):
                        qa_pairs = convert_to_qa(gemini_api_key, post_content)
                        if qa_pairs:
                            all_qa_pairs.extend(qa_pairs)
                        else:
                            st.warning(f"Failed to convert post {i+1} to Q&A format.")
                    progress_bar.progress((i + 1) / len(reddit_content))

                if all_qa_pairs:
                    df = save_to_excel([all_qa_pairs])
                    st.dataframe(df)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download data as CSV",
                        data=csv,
                        file_name="reddit_qa.csv",
                        mime="text/csv",
                    )
                    
                    
                    
                else:
                    st.error("No Q&A pairs were generated.")
            else:
                st.error(f"No posts found in r/{subreddit}")

if __name__ == "__main__":
    main()