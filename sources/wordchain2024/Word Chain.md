# Word Chain

Word Chain is a game where players take turns finding a word that starts with the last letter of the previous word. Word must be in the defined category, for example, singular nouns only, no people or geographical names. The game starts with the first player selecting a random word. The game ends when the player repeats the words previously used in the current game or fails to find a word within the time limit (5-15 seconds).  
Word Chain is also known as grab on behind, last and first, alpha and omega.   
Game parameters: category of words, time limit.

Word Chain games are based on a list of nouns, for example, a List of Singular English Nouns.

# How many singular nouns are in the English language?

This is a non-trivial question. The exact number of singular nouns in the English language is not known. Oxford English Dictionary (OED, [https://www.oed.com](https://www.oed.com)) lists around 500,000 words. The access to OED costs 100 British Pounds a year for individuals ([https://www.oed.com/purchase](https://www.oed.com/purchase)), the API key is available for purchase only for institutional accounts, and the price is not disclosed.  
The Webster's Third New International Dictionary, published in 1961, contains an estimated 476,000 entries in the 2005 edition. According to [Wikipedia](https://en.wikipedia.org/wiki/Webster%27s_Third_New_International_Dictionary), Philip Babcock Gove and a team of lexicographers spent 757 editor-years and $3.5 million to prepare this dictionary. The dictionary doesn't explicitly state the number of nouns; some estimates suggest it contains around 80,000 \- 110,000.  
And there is no answer to our question about the amount of singular nouns.  
When forced to estimate, Google’s Bard provides random numbers, like 85,738 or 350,000.  
OpenAi’s model gpt4-1106-preview: “It is impossible to provide an exact number, but there are likely tens of thousands of singular nouns in the English language.”

# List of Singular English Nouns

While even the approximate number of singular English nouns is unknown, estimating the number of nouns that can be used to play the Word Chain game is more challenging. Many nouns are related to specific fields, like medicine, biology, or chemistry. Even common nouns can be separated into several categories, depending on the age and education level, for example, nouns for kids.

There are some available resources on the Internet related to the List of Singular English Nouns (LSEN).  
Typical English courses provide examples of LSEN with a length of 10-20 words. Internet resources with a large list of nouns:

- 1000+ of the most commonly used nouns: [https://7esl.com/list-of-nouns/](https://7esl.com/list-of-nouns/)  
- Top 1500 Nouns, sorted by usage frequency: [https://www.talkenglish.com/vocabulary/top-1500-nouns.aspx](https://www.talkenglish.com/vocabulary/top-1500-nouns.aspx)  
- 1400+ nouns of 11 types with definitions: [https://momlovesbest.com/list-of-nouns](https://momlovesbest.com/list-of-nouns)  
- 10000+ Nouns from A to Z: [https://cocosteaparty.com/list-of-nouns/](https://cocosteaparty.com/list-of-nouns/), [https://greenopolis.com/list-of-nouns/](https://greenopolis.com/list-of-nouns/)   
- The Giant List of 4,640 Untouchable Nouns (copyright is claimed): [https://patternbasedwriting.com/elementary\_writing\_success/noun-suffix-list-untouchable-nouns/](https://patternbasedwriting.com/elementary_writing_success/noun-suffix-list-untouchable-nouns/)  
- List of 6,800 nouns (curated until 2019): [https://www.desiquintans.com/nounlist](https://www.desiquintans.com/nounlist)  
- 1,525 nouns in downloadable formats: [https://copylists.com/words/list-of-nouns/](https://copylists.com/words/list-of-nouns/)

Corpus of Contemporary American English ([COCA](https://www.english-corpora.org/coca/)). The Corpus of Contemporary American English (COCA) is the only large and "balanced" corpus of American English. COCA is probably the most widely-used corpus of English, and it is related to many other corpora of English that we have created. The corpus contains more than one billion words of text (25+ million words each year 1990-2019) from eight genres: spoken, fiction, popular magazines, newspapers, academic texts, TV and movies subtitles, blogs, and other web pages.

The Natural Language Toolkit (NLTK, [www.nltk.org](http://www.nltk.org)) is a suite of libraries and programs for symbolic and statistical natural language processing (NLP) for English written in Python and available for non-commercial use.   
Let us try the usability of NLTK, starting with the Webtext corpus. Simple Python code helps us to count nouns.

import nltk  
nltk.download('webtext')  
wt\_words \= nltk.corpus.webtext.words()  
is\_noun \= lambda pos: pos\[:2\] \== 'NN'  
\# convert each word to lowercase and removes duplicates before adding it to the list of all nouns  
all\_nouns \= list(set(word.lower() for (word, pos) in nltk.pos\_tag(wt\_words) if is\_noun(pos) and len(word) \> 2))  
len(all\_nouns)

The Webtext corpus contains 12,205 nouns. Let us list 10 random words from this list to see the usability. The first result is: \['sports', 'ff10x', 'calibrate', 'blah', 'qualities', 'tentacles', 'passin', 'statements', 'killin', 'climbing'\]. We can observe only the word “climbing” that can be used as a singular noun, while the other nine words are plural or questionable as a noun. Another attempt to obtain ten random words provides: \['banner68', 'claret', 'dare', 'presents', 'hiding', 'demo', 'looka', 'iran', 'kraken', 'gathering'\]. Seven out of ten results are singular nouns. After a dozen attempts, we disqualified the Webtext corpus as a source of nouns because it explores the web's strange aspects and is impractical for linguistic purposes.

Exploring the NLTK Wordnet with the following Python code:

nltk.download('wordnet')  
from nltk.corpus import wordnet  
all\_nouns \= \[x.lemmas()\[0\].name() for x in wordnet.all\_synsets('n')\]  
nouns \= list(set(word.lower() for word in all\_nouns if len(word) \> 2))  
len(nouns)

The output of the code is 67,111 nouns, which is a large number and close to the estimated 80,000. Random sampling provides \['paparazzo', 'case-fatality\_proportion', 'telanthera', 'pastinaca', 'duke', 'thermonuclear\_reaction', 'sense', 'plural', 'inside\_job', 'townsman'\]. For our purpose, we need to exclude words containing underline. 

filtered\_nouns \= \[noun for noun in nouns if "\_" not in noun\]  
len(filtered\_nouns)

Now, the filtered list contains 40,893 nouns. Sampling the new list: \['blues', 'reglaecus', 'kickapoo', 'heyse', 'fistula', 'lithiasis', 'choker', 'helotiales', 'northampton', 'aristocrat'\]. Comprehending more than half of the sampled nouns is difficult. Another sample batch of \['microfarad', 'campbell', 'jauntiness', 'zircon', 'rampage', 'clemency', 'begum', 'streptobacillus', 'first-nighter', 'usher'\] shows the necessaty to exclude words with a dash for the purpose of the Word Chain game.

filtered\_nouns \= \[noun for noun in nouns if '\_' not in noun and '-' not in noun\]

Now, the filtered list contains 39,854 nouns. Random samples: \['assize', 'irritability', 'rift', 'connecticuter', 'kanarese', 'feminism', 'jog', 'neurinoma', 'tapering', 'mohammed'\]. The list contains only singular nouns, except for some plurals, like ‘snips’, ‘mathematics’, ‘'underpants', or ‘news’, that can be used as singular nouns. For the purpose of the Word Chain game, we should separate people’s and geographical names. Also, it is necessary to separate professional nouns to control the game's difficulty level.

Wordnet provides definitions:   
wordnet.synsets('nestling')\[0\].definition() outputs ‘young bird not yet fledged’.  
Google [Cloud Natural Language API](https://cloud.google.com/natural-language/docs/classifying-text?hl=en) can be used to classify text containing a word and its definition.

Library spaCy has a more advanced Named Entity Recognition (NER) system. The \`en\_core\_sci\_sm\` model is more likely to correctly identify medical terms than the general English model \`en\_core\_web\_sm\`.  
Filtering geographical names with the following code:

import spacy  
nlp \= spacy.load("en\_core\_web\_sm")  
text \= ", ".join(filtered\_nouns) \+ '.'  \# Concatenate nouns with commas  
doc \= nlp(text) \# Process the text made of nouns  
\# Extract geographical names (GPE entities)  
geographical\_names \= \[ent.text for ent in doc.ents if ent.label\_ \== "GPE"\]  
len(geographical\_names)

There are 1,872 words identified as geographical names, however random sampling \['yoruba', 'bahai', 'tahiti', 'vagina', 'irvingia', 'mentzelia', 'cuddy', 'tarpaulin', 'vietnam', 'lycoperdon'\] shows plenty of medical and biological terms as geographical. 

Medical terms and drug names can be searched via NCBI API: [https://id.nlm.nih.gov/mesh/swagger/ui\#/lookup/lookupDescriptors](https://id.nlm.nih.gov/mesh/swagger/ui#/lookup/lookupDescriptors)  
Medical spaCy: [https://spacy.io/universe/project/medspacy](https://spacy.io/universe/project/medspacy)  
en\_core\_med7\_lg  \# Biomedical model

(my Colab [Notebook](https://colab.research.google.com/drive/18D_nbS7SgyZMubO6-8JZejyOF0swqb2y))

# Playing Word Chain with LLM

Prompt.  
You are an intelligent and terse game partner for the Word Chain game. Word Chain is a game where players take turns finding a word that starts with the last letter of the previous word. 

Game rules:  
1\. All words must be valid singular nouns in English with no people names.  
2\. Every word should be unique within a game; no repetitions are allowed.  
3\. The game starts with the user entering a random word.  
4\. You reply with a single word that starts with the last letter of the user’s word.  
5\. Now, the user must enter a word that starts with the last letter of your word.  
6\. The game continues until any player repeats the word previously used during this game or when a player cannot find a word and enters “I lost”.  
7\. No chatting is allowed during the game.  
8\. If a player breaks any rule, another player should say: “You lost, because ...” stating the reason and the game ends.

The valid word chain example is: table, elephant, tool, lamp, …

Acknowledge the above with “I am ready”.  
—

## Game Referee

Model: GPT-4-1106-preview.  
Temperature: 0\.  
Top P: 0.2.

### System prompt:

You are smart referee for the  Word Chain game. Word Chain is a game where players take turns finding a word that starts with the last letter of the previous word. 

Game rules:  
1\. All words must be valid singular nouns in English with no people names.  
2\. Every word should be unique within a game; no repetitions are allowed.  
3\. The game starts with the First Player entering a random word.  
4\. The Second Player must reply with a word that starts with the last letter of the First Player’s word.  
5\. The First Player must enter a word that starts with the last letter of the Second Player’s word.  
6\. The game continues until any player repeats the word previously used during this game or when a player cannot find a word and enters “I lost”.  
7\. No chatting is allowed during the game.  
8\. If a player breaks any rule, another player should say: “You lost, because ...” stating the reason and the game ends.

The valid word chain example is: table, elephant, tool, lamp, …

Your actions:  
Analyze the chat log (in JSON format) to:  
\- check it any game rule was broken for every player turn;   
\- print the valid part of the word chain as a numbered list;  
\- announce the winner.

—

### Experiment 1\.

Model: GPT-4-1106-preview.  
Temperature: 0\.  
Top P: 0.2.

#### System prompt:

You are an intelligent and terse game partner for the Word Chain game. Word Chain is a game where players take turns finding a word that starts with the last letter of the previous word. All words must be valid singular nouns in English with no people names. The game starts with the user entering a random word. The game continues until any player repeats the word previously used during this game or when a player cannot find a word and enters “I lost”. No chatting is allowed during the game. If a player breaks any rule, another player should say: “You lost, because ...” stating the reason and the game ends.

#### Dialogue:

\[{"role":"system","content":"You are an intelligent and terse game partner for the Word Chain game. Word Chain is a game where players take turns finding a word that starts with the last letter of the previous word. All words must be valid singular nouns in English with no people names. The game starts with the user entering a random word. The game continues until any player repeats the word previously used during this game or when a player cannot find a word and enters “I lost”. No chatting is allowed during the game. If a player breaks any rule, another player should say: “You lost, because ...” stating your reason, and the game ends."},{"role":"user","content":"deer"},{"role":"assistant","content":"ring"},{"role":"user","content":"gang"},{"role":"assistant","content":"grape"},{"role":"user","content":"eagle"},{"role":"assistant","content":"elephant"},{"role":"user","content":"trick"},{"role":"assistant","content":"kangaroo"},{"role":"user","content":"owl"},{"role":"assistant","content":"lemon"},{"role":"user","content":"no"},{"role":"assistant","content":"You lost, because \\"no\\" is not a singular noun."}\]

#### Referee judgment:

The winner is the assistant.  
The valid part of the chain is: deer, ring, gang, grape, eagle, elephant, trick, kangaroo, owl, lemon.  
The length of the valid chain part is 10 words.

—

# Turing Test

WCGT-AI: Word Chain Game Test as a Benchmark of an LLM performance.

In 1950, an English mathematician and philosopher, Alan Turing, proposed a definition and the test for the computer Artificial Intelligence \[1\]. While widely criticized, the Turing Test remains the key benchmark for Large Language Models (LLMs) until today. Challenging a computer (program) with a meaningful conversation was a progressive idea during computers’ infancy. Nowadays, LLMs can support a conversation on any topic and can be better chatting and learning partners than humans on some occasions. There have been claims of LLMs passing the Turing Test; however, the actual results and implications are still debated. The Turing Test may not be the best measure of AI intelligence, and AI research is moving towards other benchmarks.  
We propose challenging LLMs with certain language games to obtain measurable and comparable results. One of the game examples is Word Chain, where players take turns finding a word that starts with the last letter of the previous word. LLMs are still struggling with this (simple) task, and a kid can easily win a game. Word Chain Game Test (WCGT-AI) can provide a measurable result \- the chain length and can allow different LLMs to play against each other in tournaments.  
 WCGT-AI offers numerous variations in the subject or category of words and chaining rules. LLM should be capable of understanding the rules presented in the natural language and ability to follow rules to win a game.   
WCGT-AI is not the ultimate test of “intelligence”, but can serve as a benchmark, one of many, to measure the performance of LLM. Take CPU (Central Processing Unit) benchmarking as a reference.   
LLMs are built on principles similar to the Word Chain Game.

References:

1. Turing, Alan M. Computing machinery and intelligence. *Springer Netherlands*, 2009\. (Turing, A. M. Mind LIX, 433–460 (1950).)  
2. Scorza, Maristella, Erika Benassi, CLAUDIA DARIA Boni, and Giacomo Stella. "THE WORD CHAIN TEST: A SHORT COLLECTIVE SCREENING FOR IDENTIFICATION OF CHILDREN AT RISK FOR READING DISABILITIES." *TPM: Testing, Psychometrics, Methodology in Applied Psychology* 26, no. 1 (2019).

## Nouns Classification by Difficulty Level

You are a smart assistant to classify nouns. You need to analyze the CSV file, which includes the NOUN and 2 descriptions for this NOUN. You output CSV format NOUN, CLASS, where CLASS is a classification of a NOUN to one of the following types:  
\- ABR: multi-word abbreviation, ex: ATM, NATO, EU, mRNA, pH, dB, USA;  
\- NAM: name or surname or nickname of a person or pet or fictional or mythical person;  
\- GEO: geographic name of the continent, country, city, street, something typically found on a map, ex: Mexico;  
\- GNO: noun, contains geographical name, ex: Mexican, Roman;  
\- 05Y: common noun, not a name, that every 5-year-old should know, ex: dog, ball, book, tree, table;  
\- 10Y: common noun, not a name, that every 10-year-old should know, ex: sentence, angina, computer, continent;  
\- 50Y: common noun, not a name, that every adult with high-school education and live experience should know, ex: mortgage, paradigm, hypothesis, bureaucracy, plagiarism, hegemony;  
\- BIO: biology or chemistry-related term, name or noun, species, plants, bioprocess, genetics, that requires special higher education in biology major to learn this term, ex: zymolysis, aardvark, glycolysis;  
\- MED: medical term, name of a drug, medical process, words that people learn during medical major and medical practice, ex: acetaminophen, appendectomy;  
\-TEC: technical term from engineering, which is only taught in university for engineering majors, ex: thermocouple, cantilever, rheology, lagrangian, magnetostriction.

