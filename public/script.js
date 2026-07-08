// สร้างแผนที่
const map = L.map('map').setView([13.7563,100.5018],13)

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
maxZoom:19
}).addTo(map)

let marker
let markers=[]
let circles=[]

// icon หมา
const dogIcon = L.icon({
iconUrl:"/icons/dog.png",
iconSize:[32,32]
})

// icon แมว
const catIcon = L.icon({
iconUrl:"/icons/cat.png",
iconSize:[32,32]
})

// คลิกแผนที่เพื่อปักหมุด
map.on("click",(e)=>{

if(marker){
map.removeLayer(marker)
}

marker = L.marker(e.latlng).addTo(map)

document.getElementById("lat").value = e.latlng.lat
document.getElementById("lng").value = e.latlng.lng

})

// โหลดโพสต์สัตว์
async function loadPets(){

const res = await fetch("/pets")
const pets = await res.json()

const list = document.getElementById("petList")

list.innerHTML=""

pets.forEach(pet=>{

list.innerHTML += `
<div class="card">

<h3>${pet.name}</h3>

<p>${pet.type}</p>

<p>${pet.location}</p>

${pet.image ? `<img src="/uploads/${pet.image}" width="150">` : ""}

${pet.poster ? `<br><a href="/${pet.poster}" download>ดาวน์โหลดโปสเตอร์</a>` : ""}

<br>

<button onclick="deletePet('${pet._id}')">ลบ</button>

</div>
`

})

}

loadPets()

// โหลด marker + prediction area
async function loadMarkers(){

// ลบ marker เก่า
markers.forEach(m=>map.removeLayer(m))
markers=[]

// ลบวง prediction เก่า
circles.forEach(c=>map.removeLayer(c))
circles=[]

const res = await fetch("/pets")
const pets = await res.json()

pets.forEach(pet=>{

if(pet.lat && pet.lng){

let icon = dogIcon

if(pet.type === "แมว"){
icon = catIcon
}

const m = L.marker([pet.lat,pet.lng],{icon:icon}).addTo(map)

m.bindPopup(`
📍 <b>${pet.name}</b><br>
${pet.type}<br>
${pet.location}<br>
${pet.image ? `<img src="/uploads/${pet.image}" width="100">` : ""}
`)

markers.push(m)

// ---------- Prediction Area ----------

let near = 200
let mid = 500

if(pet.type === "หมา"){
near = 400
mid = 1000
}

// วงเหลือง (โอกาสสูง)
const c1 = L.circle([pet.lat,pet.lng],{
radius:near,
color:"yellow",
fillOpacity:0.25
}).addTo(map)

// วงส้ม (ปานกลาง)
const c2 = L.circle([pet.lat,pet.lng],{
radius:mid,
color:"orange",
fillOpacity:0.15
}).addTo(map)

circles.push(c1)
circles.push(c2)

}

})

}

loadMarkers()

// โพสต์สัตว์
const form = document.getElementById("petForm")

form.addEventListener("submit",async(e)=>{

e.preventDefault()

const formData = new FormData(form)

const res = await fetch("/pets",{
method:"POST",
body:formData
})

await res.json()

form.reset()

loadPets()
loadMarkers()

})

// ลบโพสต์
async function deletePet(id){

await fetch("/pets/"+id,{
method:"DELETE"
})

loadPets()
loadMarkers()

}