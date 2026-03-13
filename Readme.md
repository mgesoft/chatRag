docker compose up --build -d
docker exec -it ollama ollama pull deepseek-r1:1.5b
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it rag_api python ingest.py

Servicio URL💬 Chat web [http://localhost:8000](http://localhost:8000)

🧠 API RAG [http://localhost:8000/docs](http://localhost:8000/docs)

 Dashboard [http://localhost:8501](http://localhost:8501)

# Instalacion sin dockers

## Instalar Ollama en local 

Instalar Ollama : https://ollama.com/

Subir modelo (actual: llama 3.1). Si se cambia el modelo hay que cambiar el código.

````ollama pull llama3.1````

Subir modelo embed:

````ollama pull nomic-embed-text````



# Distribuir

##  chatUsar conda-pack:

conda install -c conda-forge conda-pack

conda-pack -n chatragpcwideum -o chatragconda.zip --format zip 

conda-pack -n ClassifyPython -o ImageClassification/ClassifyPython.zip --format zip

donde ClassifyPython es el entorno python,

para instalar:

descomprimir el zip

ejecutar conda-unpack que esta en scrips,

copiar en un direcorio la APP, por ejemplo Classificador. copiar aqui los scrips python y data

para ejecutar : 

python.exe ./Apps/Clasificador/main.py modelid=174 basefolder=E:\Supervisor validationset=20 images=images trainings=Trainings models=Trainings epochs=3 batchsize=32 augmented=1 trainingid=0


## Exportar un entorno conda:

conda env export --no-builds > environment.yml   

y para crearlo en destino:

conda env create -f environment.yml   


