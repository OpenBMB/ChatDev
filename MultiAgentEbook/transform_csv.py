import pandas as pd

input_file = 'papers.csv'
df_raw = pd.read_csv(input_file, on_bad_lines='warn')

cat2id = {'Communication':'1',
          'Organization':'2',
          'Evolution':'3',
          'Simulation':'4'}

for cat in ['Communication','Evolution','Simulation','Organization']:
    df = df_raw[df_raw['AwesomeListCategory'] == cat]

    new_df = pd.DataFrame(columns=['image_path','title','author','summary','affiliation'])

    index = 0

    first_title = df.iloc[0]['Title']
    first_author = df.iloc[0]['Authors']
    first_affiliation = df.iloc[0]['Affiliation']
    first_summary = df.iloc[0]['Abstract'].replace("\n","")
    first_cover_path = "./images/" + cat2id[cat] + "d.png"

    first_line = pd.DataFrame([[first_cover_path,first_title,first_author,first_summary,first_affiliation]], columns=['image_path','title','author','summary','affiliation'])
    new_df = pd.concat([new_df, first_line], ignore_index=True)
    image_path_list = df['PaperIndex'].tolist()
    for _, line in df[1:].iterrows():
        print(line['Title'])
        new_line = pd.DataFrame([["./images/{}.png".format(image_path_list[index]),line['Title'],line['Authors'],str(line['Abstract']).replace("\n",""),line['Affiliation']]], columns=['image_path','title','author','summary','affiliation'])
        new_df = pd.concat([new_df, new_line], ignore_index=True)
        index += 1

    last_line = pd.DataFrame([["./images/{}.png".format(image_path_list[index]),"To be Continued...","Your Contributions are Welcome!","",""]], columns=['image_path','title','author','summary','affiliation'])
    new_df = pd.concat([new_df, last_line], ignore_index=True)

    new_df.to_csv("./book_{}/data.csv".format(cat.lower()))
