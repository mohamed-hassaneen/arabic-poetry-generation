# Arabic Poetry Generation (fine-tuned google/gemma-3-270m)
Fine-tuned google/gemma-3-270m for generating Arabic poetry.

So far, I've done:

1. **Reading**: I read this paper on fine-tuning AraGPT2 for Arabic poem generation ([link](https://link.springer.com/article/10.1007/s13369-023-07692-1)). 

2. **Data Prep**: Instead of crawling Al Diwan or other similar websites myself, I downloaded 'APCD.csv' (the dataset mentioned in the paper, found [here](https://hci-lab.github.io/ArabicPoetry-1-Private/#PCD)) and wrote a script ('prepare_data.py') to handle the preprocessing steps mentioned in the paper (removing tashkeel, restricting to the valid 16 meters, formatting verses as '[rhyme] h2 [meter] h1, etc...). 
   * Training data produced by my script: [Link](https://drive.google.com/file/d/1d8Lks1TowMwyqEutloPnDI9ggHNJIu3r/view?usp=drive_link)
   * Validation data produced by my script: [Link](https://drive.google.com/file/d/1TZQBnBNA11syETDzqjQHod2KE8AmlJKe/view?usp=drive_link)

3. **Fine-Tuning**: I tried to fine-tune `google/gemma-3-270m` using LoRA so I wouldn't have to train all the base weights. However, I couldn't complete a real training run due to resource limitations. I barely had any free compute left on Google Colab after finishing my DL assignment. To at least test my pipeline, I trained it on arbitary hyperparameters using only 10% of the training data and for only 1 epoch and published the model to Hugging Face ([Link](https://huggingface.co/mohamed-hassaneen/gemma3-arabic-poetry))

4. **Results**: Because of the compute limits and arbitary hyperparameters, the model obviously returns garbage right now (as can be seen from the output of the 'Evaluate Perplexity' and 'Test Generation' cells)

5. **Interface**: I explored building a simple Gradio interfaces for the app, but I didn't push it to the repo since the model
currently returns garbage anyway

The code for the data preparation and the training pipeline is included in the repo.