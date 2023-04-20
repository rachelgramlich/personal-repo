#Purpose: Input link to webpage containing recipe and output grocery list
#Author: Rachel Gramlich
#Date Updated: 2023-04-20
#Enhancements
    # intake from google form, add tic marks and brackets to list
    # output length of cooking time
    # output cooking method (oven, stove, etc)
    # output to email or something, ideally note in phone, or copy to clipboard
    # create dataframe out of ingredients - with name,amount,unit as columns. cut down ingredients to basics (e.g. rice instead of "Steamed rice, such as jasmine or basmati, for serving"), and consolidate across recipes, adding quantities
    # try to create dataframe of all ingredients https://kzz.medium.com/how-i-automated-the-creation-of-my-grocery-list-from-a-bunch-of-recipe-websites-with-python-90d15e5c0c83

#imports
import re
import requests
from bs4 import BeautifulSoup

#input recipe urls here
url_list = ['https://www.simplyrecipes.com/recipes/banana_bread/'
            ,'https://cooking.nytimes.com/recipes/1020045-coconut-miso-salmon-curry?action=click&module=RecipeBox&pgType=recipebox-page&region=collection&rank=19'
           ]

#create function that intakes a list of recipe urls and outputs ingredient list for each url
for url in url_list:
    
    #send a 'get' request to the URL and fetch the webpage content
    webpage_html = requests.get(url)

    #parse the webpage content using Beautiful Soup
    webpage_html_parsed = BeautifulSoup(webpage_html.content, 'html.parser')

    #find recipe name
    recipe_name = webpage_html_parsed.find('h1').text.strip()

    #search for section titles that might contain the list of ingredients 
    #^ matches beginning of the string, h denotes heading
    #\d matches any unicode decimal digit
    section_titles = webpage_html_parsed.find_all(re.compile('^h\d'), string=re.compile('Ingredients', re.IGNORECASE))

    #look for the next <ul> (unordered list) or <ol> (ordered list) element after each section title
    ingredients = []
    for title in section_titles:
        next_element = title.find_next()
        while next_element is not None and next_element.name not in ['ul', 'ol']:
            next_element = next_element.find_next()
        if next_element is not None:
            for ingredient in next_element.find_all('li'):
                ingredients.append(ingredient.text.strip())

    #print the list of ingredients as a bulleted list
    if ingredients:
        print(recipe_name)
        for i in ingredients:
            print('  ' + i)
    else:
        print("Could not find the list of ingredients on the webpage.")
